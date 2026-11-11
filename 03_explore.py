"""Step 3: maps, global Moran's I, and LISA clusters (Research Question 1)."""
import json

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from ceb import config, explore, geo

CLUSTER_COLORS = {"High-High": "#b2182b", "Low-Low": "#2166ac", "High-Low": "#f4a582",
                  "Low-High": "#92c5de", "Not significant": "#e8e8e8"}

if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    gdf = gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True)

    # Choropleth of burden
    fig, ax = plt.subplots(figsize=(7, 9))
    gdf.plot(column="burden_pct", scheme="Quantiles", k=5, cmap="OrRd", legend=True,
             legend_kwds={"title": "Energy burden (%)", "loc": "upper right"},
             edgecolor="white", linewidth=0.2, ax=ax)
    ax.set_axis_off()
    ax.set_title("Household energy burden by census tract, Chicago (LEAD 2022)")
    fig.savefig(config.FIGURES / "map_burden.png", dpi=200, bbox_inches="tight")

    results = {}
    for kind in ("queen", "knn"):
        w = geo.weights(gdf, kind)
        results[kind] = explore.global_moran(gdf["burden_pct"], w)
        print(f"Global Moran's I ({kind}): {results[kind]['I']:.3f}, p = {results[kind]['p_sim']:.4f}")

    w = geo.weights(gdf, "queen")
    lisa = explore.lisa(gdf, "burden_pct", w)
    gdf = gdf.merge(lisa, on="GEOID")
    counts = gdf["cluster"].value_counts().to_dict()
    results["lisa_fdr_cutoff"] = lisa.attrs["fdr_cutoff"]
    results["lisa_counts_fdr"] = counts
    results["lisa_counts_raw_p05"] = gdf.loc[gdf["sig_raw"], "quadrant"].value_counts().to_dict()
    print("LISA clusters (FDR):", counts)

    order = list(CLUSTER_COLORS)
    gdf["cluster"] = gdf["cluster"].astype("category").cat.set_categories(order)
    fig, ax = plt.subplots(figsize=(7, 9))
    gdf.plot(column="cluster", categorical=True, cmap=ListedColormap(list(CLUSTER_COLORS.values())),
             legend=True, legend_kwds={"loc": "upper right", "title": "LISA cluster (FDR 5%)"},
             edgecolor="white", linewidth=0.2, ax=ax)
    ax.set_axis_off()
    ax.set_title("Energy burden clusters, Chicago census tracts")
    fig.savefig(config.FIGURES / "map_lisa.png", dpi=200, bbox_inches="tight")

    gdf[["GEOID", "burden_pct", "local_I", "p_sim", "quadrant", "cluster"]].to_csv(
        config.TABLES / "lisa_clusters.csv", index=False)
    (config.TABLES / "moran.json").write_text(json.dumps(results, indent=2, default=float))
    print("Saved maps to output/figures and tables to output/tables")
