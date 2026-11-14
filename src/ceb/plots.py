"""Shared helpers for static maps and figures.

Every static map gets the same context layers so readers can orient
themselves: Lake Michigan and rivers, the city boundary, and the 77 Chicago
community areas (with optional name labels). Layers are skipped quietly if
their raw files have not been downloaded.
"""
from functools import lru_cache

import geopandas as gpd
import matplotlib.pyplot as plt

from . import config

WATER = "#cfe0ec"
TEXT = "#222222"


@lru_cache(maxsize=1)
def _layers():
    out = {}
    ca = config.RAW / "chicago_community_areas.geojson"
    if ca.exists():
        g = gpd.read_file(ca).to_crs(config.PROJECTED_CRS)
        col = next(c for c in g.columns if c.lower() in ("community", "name", "community_area"))
        g["name"] = g[col].astype(str).map(tidy_name)
        out["areas"] = g[["name", "geometry"]]
    places = config.RAW / f"tiger_places_{config.TIGER_YEAR}"
    if places.exists():
        p = gpd.read_file(next(places.rglob("*.shp")))
        out["city"] = p[p["GEOID"] == config.CHICAGO_PLACE_GEOID].to_crs(config.PROJECTED_CRS)
    water = config.RAW / f"tiger_water_{config.TIGER_YEAR}"
    if water.exists():
        w = gpd.read_file(next(water.rglob("*.shp"))).to_crs(config.PROJECTED_CRS)
        out["water"] = w[w.area > 40_000]
    return out


def tidy_name(s):
    """'MCKINLEY PARK' -> 'McKinley Park'; 'OHARE' -> "O'Hare"."""
    t = s.strip().title()
    t = " ".join(("Mc" + w[2:].title()) if w.startswith("Mc") and len(w) > 2 else w for w in t.split())
    return {"Ohare": "O'Hare", "Loop": "The Loop"}.get(t, t)


def community_areas():
    return _layers().get("areas")


def base_map(gdf, figsize=(7, 9)):
    """Figure and axes framed on the tracts, with water drawn underneath."""
    fig, ax = plt.subplots(figsize=figsize)
    g = gdf.to_crs(config.PROJECTED_CRS)
    xmin, ymin, xmax, ymax = g.total_bounds
    pad = 0.03 * max(xmax - xmin, ymax - ymin)
    layers = _layers()
    if "water" in layers:
        layers["water"].plot(ax=ax, color=WATER, linewidth=0, zorder=0)
    ax.set_xlim(xmin - pad, xmax + pad + 2500)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_axis_off()
    return fig, ax


def add_context(ax, labels=None, label_size=5.5):
    """City boundary, community-area outlines, and optional area name labels.

    labels: None for no labels, "all" for every area, or a list of area names.
    """
    layers = _layers()
    if "areas" in layers:
        layers["areas"].boundary.plot(ax=ax, color="#333333", linewidth=0.35, alpha=0.6, zorder=3)
    if "city" in layers:
        layers["city"].boundary.plot(ax=ax, color="#111111", linewidth=0.8, zorder=4)
    if labels and "areas" in layers:
        a = layers["areas"]
        if labels != "all":
            a = a[a["name"].isin(labels)]
        for _, r in a.iterrows():
            p = r.geometry.representative_point()
            ax.annotate(r["name"], (p.x, p.y), ha="center", va="center", fontsize=label_size, color=TEXT,
                        zorder=6, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.65))
    lake = layers.get("water")
    if lake is not None and len(lake):
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ax.text(x1 - 0.05 * (x1 - x0), y0 + 0.62 * (y1 - y0), "LAKE\nMICHIGAN", ha="right", va="center",
                fontsize=8, color="#4b7598", style="italic", zorder=6)


def area_of_tracts(gdf):
    """Community area name for each tract (by its interior point)."""
    areas = community_areas()
    if areas is None:
        return None
    g = gdf.to_crs(config.PROJECTED_CRS)
    pts = gpd.GeoDataFrame({"GEOID": g["GEOID"].to_numpy()}, geometry=g.geometry.representative_point(),
                           crs=g.crs)
    j = gpd.sjoin(pts, areas, how="left", predicate="within").drop_duplicates("GEOID")
    return j.set_index("GEOID")["name"].reindex(g["GEOID"]).to_numpy()


def save(fig, name, source="LEAD 2022 (U.S. DOE); ACS 2018-2022; TIGER/Line; City of Chicago community areas."):
    fig.text(0.01, 0.005, f"Source: {source}", fontsize=6, color="#666666")
    fig.savefig(config.FIGURES / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
