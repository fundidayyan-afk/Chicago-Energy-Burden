"""Write a fake 'city' into data/raw so the pipeline can be tested offline.

Usage (from a scratch copy of the repo, never your real data folder):
    python tests/make_synthetic_data.py
Burden is built to cluster in the southwest corner, so Moran's I should be
clearly positive and the LISA map should show a High-High cluster there.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box

from ceb import config
from ceb.download import ACS_VARS

rng = np.random.default_rng(1)
N = 28
size = 1000.0
cells, ids = [], []
for i in range(N):
    for j in range(N):
        cells.append(box(i * size, j * size, (i + 1) * size, (j + 1) * size))
        ids.append(f"17031{i:03d}{j:03d}")
tr = gpd.GeoDataFrame({"GEOID": ids, "COUNTYFP": "031", "NAMELSAD": ids, "ALAND": size**2},
                      geometry=cells, crs=config.PROJECTED_CRS)
place = gpd.GeoDataFrame({"GEOID": [config.CHICAGO_PLACE_GEOID]},
                         geometry=[box(0, 0, N * size - 1500, N * size)], crs=config.PROJECTED_CRS)
for name, g in [("tracts", tr), ("places", place)]:
    d = config.RAW / f"tiger_{name}_{config.TIGER_YEAR}"
    d.mkdir(parents=True, exist_ok=True)
    g.to_crs("EPSG:4269").to_file(d / f"fake_{name}.shp")

# Smooth "disadvantage" surface, high in the southwest.
xy = np.array([[c.centroid.x, c.centroid.y] for c in cells]) / (N * size)
dis = np.exp(-((xy[:, 0] - 0.2) ** 2 + (xy[:, 1] - 0.25) ** 2) / 0.05) + rng.normal(0, 0.08, len(ids))

brackets = [("0-30%", 0.3), ("30-60%", 0.6), ("60-80%", 0.85), ("80-100%", 1.1), ("100%+", 2.2)]
rows = []
for gid, d in zip(ids, dis):
    for label, mult in brackets:
        units = int(rng.integers(40, 250) * (1 + d if mult < 1 else 1 - 0.5 * d))
        inc = 75_000 * mult * (1 - 0.4 * d)
        cost = 1_900 * (1 + 0.35 * d) * (0.8 + 0.2 * mult)
        rows.append({"FIP": gid, "AMI150": label, "UNITS": max(units, 0),
                     "HINCP*UNITS": inc * units, "ELEP*UNITS": 0.55 * cost * units,
                     "GASP*UNITS": 0.42 * cost * units, "FULP*UNITS": 0.03 * cost * units})
lead_dir = config.RAW / "lead_il_2022"
lead_dir.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(lead_dir / "IL AMI Census Tracts 2022.csv", index=False)

acs = {"GEOID": ids, "NAME": ids}
base = {"pop_total": 3000, "occ_units": 1200, "units_total_yb": 1300, "units_total_str": 1300,
        "heat_total": 1200, "pov_universe": 2900}
for code, name in ACS_VARS.items():
    if name in base:
        e = np.full(len(ids), base[name], float)
    elif name == "med_hh_income":
        e = 75_000 * (1 - 0.45 * dis)
    elif name == "med_year_built":
        e = 1955 - 15 * dis
    elif name.startswith("pop_"):
        e = 3000 * np.clip(rng.uniform(0.05, 0.4, len(ids)) + 0.3 * dis * (name == "pop_nh_black"), 0, 0.9)
    elif name.startswith("units_") or name.startswith("renter"):
        e = 1200 * np.clip(rng.uniform(0.05, 0.3, len(ids)) + 0.2 * dis, 0, 0.9) / 2
    else:
        e = 1200 * rng.uniform(0.05, 0.4, len(ids))
    acs[f"{code}E"] = np.round(e)
    acs[f"{code}M"] = np.round(0.12 * e + 20)
pd.DataFrame(acs).to_csv(config.RAW / f"acs5_{config.ACS_YEAR}_tracts.csv", index=False)
print(f"Synthetic city written to {config.RAW} ({len(ids)} tracts)")
