"""Step 12: Chicago Energy Benchmarking data as supporting context.

The benchmarking ordinance covers buildings of roughly 50,000 square feet and
larger, so this describes large multifamily buildings, not the bungalows and
two-flats where many households live. It is context, not a household measure.

Questions:
  - Do large multifamily buildings in high-burden cluster tracts use more
    energy per square foot (site EUI) than those elsewhere?
  - Does energy intensity rise with building age, as the gas-burden models suggest?
  - Across tracts with several benchmarked buildings, does median building
    intensity track LEAD burden?

Outputs: output/tables/benchmarking_summary.json, benchmarking_by_cluster.csv,
benchmarking_by_era.csv. Columns are matched by pattern and logged, because
the city has renamed fields between releases.
"""
import json
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from ceb import config


def col(df, *patterns, required=True):
    for p in patterns:
        hit = [c for c in df.columns if re.search(p, c, flags=re.I)]
        if hit:
            return hit[0]
    if required:
        raise KeyError(f"No column matching {patterns}. Columns: {list(df.columns)}")
    return None


if __name__ == "__main__":
    path = config.RAW / "chicago_energy_benchmarking.csv"
    out_json = config.TABLES / "benchmarking_summary.json"
    if not path.exists():
        out_json.write_text(json.dumps({"error": "benchmarking data not downloaded"}, indent=2))
        print("No benchmarking data; skipped")
        raise SystemExit(0)

    raw = pd.read_csv(path, low_memory=False)
    print(f"Benchmarking rows: {len(raw):,}; columns: {list(raw.columns)}")
    c_year = col(raw, r"^data_?year$", r"year$")
    c_type = col(raw, r"primary_?property_?type", r"property_?type")
    c_eui = col(raw, r"^site_?eui", r"site.*eui")
    c_gas = col(raw, r"natural_?gas_?use", required=False)
    c_area = col(raw, r"gross_?floor_?area", r"floor_?area")
    c_built = col(raw, r"year_?built")
    c_lat, c_lon = col(raw, r"^latitude"), col(raw, r"^longitude")
    print(f"Using: year={c_year}, type={c_type}, eui={c_eui}, gas={c_gas}, area={c_area}, built={c_built}, "
          f"lat={c_lat}, lon={c_lon}")

    df = raw.copy()
    for c in (c_year, c_eui, c_area, c_built, c_lat, c_lon) + ((c_gas,) if c_gas else ()):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    years = df.groupby(c_year).size()
    year = int(years[years >= 500].index.max())   # latest year with broad reporting
    mf = df[(df[c_year] == year) & df[c_type].astype(str).str.contains("multifamily", case=False)]
    mf = mf[(mf[c_eui] > 0) & (mf[c_eui] < 500) & mf[c_lat].notna() & mf[c_lon].notna()].copy()
    if c_gas:
        mf["gas_intensity"] = mf[c_gas] / mf[c_area]
    print(f"Multifamily buildings reporting in {year}: {len(mf):,}")

    pts = gpd.GeoDataFrame(mf, geometry=gpd.points_from_xy(mf[c_lon], mf[c_lat]), crs="EPSG:4326")
    tracts = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    tracts = tracts[tracts["in_main_sample"].astype(bool)]
    lisa = pd.read_csv(config.TABLES / "lisa_clusters.csv", dtype={"GEOID": str})
    tracts = tracts.merge(lisa[["GEOID", "cluster"]], on="GEOID", how="left")
    j = gpd.sjoin(pts.to_crs(tracts.crs), tracts[["GEOID", "cluster", "burden_pct", "geometry"]],
                  how="inner", predicate="within")
    j["era"] = pd.cut(j[c_built], [0, 1949, 1979, 3000], labels=["Before 1950", "1950-1979", "1980 or later"])

    agg = {"buildings": (c_eui, "size"), "median_site_eui": (c_eui, "median")}
    if c_gas:
        agg["median_gas_kbtu_per_sqft"] = ("gas_intensity", "median")
    by_cluster = j.groupby("cluster").agg(**agg)
    by_era = j.groupby("era", observed=True).agg(**agg)
    by_cluster.to_csv(config.TABLES / "benchmarking_by_cluster.csv")
    by_era.to_csv(config.TABLES / "benchmarking_by_era.csv")

    t = j.groupby("GEOID").agg(n=(c_eui, "size"), eui=(c_eui, "median"), burden=("burden_pct", "first"))
    t3 = t[t["n"] >= 3]
    hh = j.loc[j["cluster"] == "High-High", c_eui]
    rest = j.loc[j["cluster"] != "High-High", c_eui]
    from scipy.stats import mannwhitneyu
    summary = {
        "data_year": year,
        "multifamily_buildings": int(len(j)),
        "tracts_with_buildings": int(t.shape[0]),
        "median_site_eui_high_burden_clusters": float(hh.median()) if len(hh) else None,
        "median_site_eui_elsewhere": float(rest.median()),
        "buildings_in_high_burden_clusters": int(len(hh)),
        "mann_whitney_p": float(mannwhitneyu(hh, rest).pvalue) if len(hh) > 5 else None,
        "tracts_with_3plus_buildings": int(len(t3)),
        "spearman_tract_eui_vs_burden": float(t3["eui"].corr(t3["burden"], method="spearman")) if len(t3) > 10 else None,
        "columns_used": {"year": c_year, "type": c_type, "site_eui": c_eui, "gas": c_gas, "area": c_area,
                         "year_built": c_built},
        "note": "Buildings of about 50,000 sq ft and up only; supporting context, not a household measure.",
    }
    src = config.RAW / "chicago_energy_benchmarking_source.json"
    if src.exists():
        summary["source"] = json.loads(src.read_text())
    out_json.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("By cluster\n" + by_cluster.round(1).to_string())
    print("By era\n" + by_era.round(1).to_string())
