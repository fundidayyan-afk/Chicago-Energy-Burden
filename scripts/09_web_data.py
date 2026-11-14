"""Step 9: export map data for the portfolio web map.

Outputs (committed, read by the website straight from GitHub):
  output/web/tracts.geojson   simplified tract shapes + the values the map shows
  output/web/summary.json     headline numbers for the page
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd

from shapely.geometry import box

from ceb import config


def tidy_name(s):
    """'MCKINLEY PARK' -> 'McKinley Park'; 'OHARE' -> "O'Hare"."""
    t = s.strip().title()
    t = " ".join(("Mc" + w[2:].title()) if w.startswith("Mc") and len(w) > 2 else w for w in t.split())
    return {"Ohare": "O'Hare", "Loop": "The Loop"}.get(t, t)

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

    # Community area for each tract (by the tract's interior point) and basemap layers
    out = out.to_crs(config.PROJECTED_CRS)
    ca_path = config.RAW / "chicago_community_areas.geojson"
    if ca_path.exists():
        ca = gpd.read_file(ca_path).to_crs(config.PROJECTED_CRS)
        name_col = next(c for c in ca.columns if c.lower() in ("community", "name", "community_area"))
        ca["name"] = ca[name_col].astype(str).map(tidy_name)
        pts = out[["id"]].copy()
        pts["geometry"] = out.geometry.representative_point()
        pts = gpd.GeoDataFrame(pts, geometry="geometry", crs=out.crs)
        joined = gpd.sjoin(pts, ca[["name", "geometry"]], how="left", predicate="within")
        out["area"] = joined.drop_duplicates("id").set_index("id")["name"].reindex(out["id"]).to_numpy()
        ca_out = ca[["name", "geometry"]].copy()
        ca_out["geometry"] = ca_out.geometry.simplify(20, preserve_topology=True)
        lp = ca_out.geometry.representative_point().to_crs("EPSG:4326")
        ca_out["lat"], ca_out["lng"] = lp.y.round(5), lp.x.round(5)
        ca_out.to_crs("EPSG:4326").to_file(WEB / "community_areas.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
        print(f"Community areas: {len(ca_out)}; tracts matched: {out['area'].notna().sum()}")
    else:
        print("No community area file; tracts will carry no area name")

    places = gpd.read_file(next((config.RAW / f"tiger_places_{config.TIGER_YEAR}").rglob("*.shp")))
    city = places[places["GEOID"] == config.CHICAGO_PLACE_GEOID].to_crs(config.PROJECTED_CRS)[["geometry"]]
    city["geometry"] = city.geometry.simplify(20, preserve_topology=True)
    city.to_crs("EPSG:4326").to_file(WEB / "city.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    water_dir = config.RAW / f"tiger_water_{config.TIGER_YEAR}"
    if water_dir.exists():
        water = gpd.read_file(next(water_dir.rglob("*.shp"))).to_crs(config.PROJECTED_CRS)
        frame = box(*city.buffer(6000).total_bounds)
        water = water[water.intersects(frame)].copy()
        water["geometry"] = water.geometry.intersection(frame)
        name = water["FULLNAME"].fillna("")
        water["kind"] = np.where(name.str.contains("Lake Michigan"), "lake", "water")
        water = water[(water["kind"] == "lake") | (water.area > 40_000)]
        water = water.dissolve(by="kind").reset_index()[["kind", "geometry"]]
        water["geometry"] = water.geometry.simplify(15, preserve_topology=True)
        water.to_crs("EPSG:4326").to_file(WEB / "water.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
        print(f"Water layers: {water['kind'].tolist()}")

    # Simplify in meters (about 15 m tolerance), then to web coordinates.
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
