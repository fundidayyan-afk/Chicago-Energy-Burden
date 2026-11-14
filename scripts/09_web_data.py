"""Step 9: export map data for the portfolio web map.

Outputs (committed, read by the website straight from GitHub):
  output/web/tracts.geojson   simplified tract shapes + the values the map shows
  output/web/summary.json     headline numbers for the page
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd

from ceb import config

WEB = config.OUTPUT / "web"
WEB.mkdir(parents=True, exist_ok=True)

FIELDS = {  # column in the build -> short key in the web file, decimals
    "burden_pct": ("burden", 2),
    "li_burden_pct": ("li_burden", 2),
    "share_high": ("share6", 3),
    "share_severe": ("share10", 3),
    "avg_energy_cost": ("cost", 0),
    "med_hh_income": ("income", 0),
    "pct_black": ("black", 1),
    "pct_hispanic": ("hispanic", 1),
    "pct_pre1950": ("pre1950", 1),
    "pct_renter": ("renter", 1),
    "pct_multifam5": ("multifam", 1),
    "households": ("households", 0),
}

if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    sample = gdf[gdf["in_main_sample"].astype(bool)].copy()

    lisa = pd.read_csv(config.TABLES / "lisa_clusters.csv", dtype={"GEOID": str})
    sample = sample.merge(lisa[["GEOID", "cluster"]], on="GEOID", how="left")
    mg = config.TABLES / "mgwr_coefficients.csv"
    if mg.exists():
        m = pd.read_csv(mg, dtype={"GEOID": str})[["GEOID", "ln_income"]].rename(columns={"ln_income": "mgwr_income"})
        sample = sample.merge(m, on="GEOID", how="left")

    out = gpd.GeoDataFrame({"id": sample["GEOID"],
                            "name": sample["NAMELSAD"].str.replace("Census Tract ", "Tract ", regex=False)},
                           geometry=sample.geometry, crs=sample.crs)
    for col, (key, nd) in FIELDS.items():
        out[key] = sample[col].round(nd)
    out["cluster"] = sample["cluster"].fillna("Not significant")
    if "mgwr_income" in sample:
        out["mgwr_income"] = sample["mgwr_income"].round(3)

    # Simplify in meters (about 15 m tolerance), then to web coordinates.
    out = out.to_crs(config.PROJECTED_CRS)
    out["geometry"] = out.geometry.simplify(15, preserve_topology=True)
    out = out.to_crs("EPSG:4326")
    path = WEB / "tracts.geojson"
    out.to_file(path, driver="GeoJSON", COORDINATE_PRECISION=5)

    hh = sample["households"]
    li = sample.dropna(subset=["li_burden_pct"])
    moran = json.loads((config.TABLES / "moran.json").read_text())
    summary = {
        "tracts": int(len(sample)),
        "households": int(round(hh.sum())),
        "citywide_burden": round(100 * sample["energy_total"].sum() / sample["income_total"].sum(), 1),
        "low_income_burden": round(100 * li["li_energy_total"].sum() / li["li_income_total"].sum(), 1),
        "households_above_10": int(round((sample["share_severe"] * hh).sum())),
        "morans_i": round(moran["queen"]["I"], 2),
        "hotspot_tracts": int((sample["cluster"] == "High-High").sum()),
        "coldspot_tracts": int((sample["cluster"] == "Low-Low").sum()),
        "data_year": "LEAD 2022, ACS 2018-2022",
        "updated": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d"),
    }
    (WEB / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.2f} MB)")
