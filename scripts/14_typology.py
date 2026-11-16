"""Step 14: neighborhood typology (k-means on tract characteristics).

Groups tracts into types with similar burden, costs, income, demographics,
and housing, so the paper can describe kinds of places rather than single
variables. Features are standardized; k is chosen by the mean silhouette
score over k = 3..8 (Rousseeuw, 1987), with 50 random starts per k.

Outputs: output/tables/typology_profiles.csv, typology_silhouette.csv,
typology_by_cluster.csv, typology_tracts.csv; output/figures/map_typology.png
(small multiples: one panel per type, so no category colors need telling apart).
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from ceb import config, plots

FEATURES = {
    "burden_pct": "Energy burden (%)",
    "ln_avg_energy_cost": "ln(average energy cost)",
    "ln_income": "ln(median income)",
    "pct_black": "% Black",
    "pct_hispanic": "% Hispanic",
    "pct_pre1950": "% built before 1950",
    "pct_renter": "% renter-occupied",
    "pct_multifam5": "% in 5+ unit buildings",
    "pct_elec_heat": "% heated by electricity",
}
SHORT = {"burden_pct": "burden", "ln_avg_energy_cost": "energy bills", "ln_income": "income",
         "pct_black": "Black share", "pct_hispanic": "Hispanic share", "pct_pre1950": "pre-1950 housing share",
         "pct_renter": "renter share", "pct_multifam5": "large-building share", "pct_elec_heat": "electric-heat share"}
ACCENT, BASE = "#2a78d6", "#e4e3df"


def describe(z_row):
    """Plain label from the type's most distinctive features (largest |z|)."""
    top = z_row.drop("burden_pct").abs().sort_values(ascending=False).index[:2]
    level = "High" if z_row["burden_pct"] > 0.5 else "Low" if z_row["burden_pct"] < -0.5 else "Moderate"
    parts = [f"{'high' if z_row[t] > 0 else 'low'} {SHORT[t]}" for t in top]
    return f"{level} burden: {parts[0]}, {parts[1]}"


if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    gdf = gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True)
    gdf["ln_avg_energy_cost"] = np.log(gdf["avg_energy_cost"])
    gdf = gdf.dropna(subset=list(FEATURES)).reset_index(drop=True)
    X = StandardScaler().fit_transform(gdf[list(FEATURES)])

    scores = []
    for k in range(3, 9):
        km = KMeans(n_clusters=k, n_init=50, random_state=config.SEED).fit(X)
        scores.append({"k": k, "silhouette": silhouette_score(X, km.labels_), "inertia": km.inertia_})
    scores = pd.DataFrame(scores)
    scores.to_csv(config.TABLES / "typology_silhouette.csv", index=False)
    k = int(scores.loc[scores["silhouette"].idxmax(), "k"])
    print(scores.round(3).to_string(index=False), f"\nChosen k = {k}")

    km = KMeans(n_clusters=k, n_init=50, random_state=config.SEED).fit(X)
    gdf["type_raw"] = km.labels_
    z = pd.DataFrame(X, columns=list(FEATURES)).assign(type_raw=km.labels_).groupby("type_raw").mean()
    order = z["burden_pct"].sort_values(ascending=False).index          # Type 1 = highest burden
    rename = {raw: i + 1 for i, raw in enumerate(order)}
    gdf["type"] = gdf["type_raw"].map(rename)
    z.index = z.index.map(rename)
    z = z.sort_index()

    raw = gdf.groupby("type")[list(FEATURES) + ["households"]].agg(
        {**{f: "mean" for f in FEATURES}, "households": "sum"})
    raw["tracts"] = gdf.groupby("type").size()
    raw["median_income"] = np.exp(raw.pop("ln_income"))
    raw["avg_energy_cost"] = np.exp(raw.pop("ln_avg_energy_cost"))
    raw["label"] = [describe(z.loc[t]) for t in raw.index]
    lisa = pd.read_csv(config.TABLES / "lisa_clusters.csv", dtype={"GEOID": str})
    gdf = gdf.merge(lisa[["GEOID", "cluster"]], on="GEOID", how="left")
    raw["share_in_high_burden_clusters"] = gdf.groupby("type")["cluster"].apply(lambda s: (s == "High-High").mean())
    raw.round(3).to_csv(config.TABLES / "typology_profiles.csv")
    pd.crosstab(gdf["type"], gdf["cluster"]).to_csv(config.TABLES / "typology_by_cluster.csv")
    gdf[["GEOID", "type"]].to_csv(config.TABLES / "typology_tracts.csv", index=False)
    print(raw.round(2).to_string())

    # Small multiples: each panel highlights one type in the accent color
    ncol = k if k <= 4 else 3
    nrow = int(np.ceil(k / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 5.2 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for i, t in enumerate(raw.index):
        ax = axes[i]
        sub = gdf[gdf["type"] == t]
        xmin, ymin, xmax, ymax = gdf.total_bounds
        gdf.plot(ax=ax, color=BASE, edgecolor="white", linewidth=0.15)
        sub.plot(ax=ax, color=ACCENT, edgecolor="white", linewidth=0.15)
        ax.set_xlim(xmin, xmax + 2500)
        ax.set_ylim(ymin, ymax)
        ax.set_axis_off()
        r = raw.loc[t]
        ax.set_title(f"Type {t}: {r['label']}\n{int(r['tracts'])} tracts; burden {r['burden_pct']:.1f}%; "
                     f"income ${r['median_income']:,.0f}", fontsize=8.5, loc="left")
    for ax in axes[k:]:
        ax.set_axis_off()
    fig.suptitle("Neighborhood types, Chicago census tracts (k-means on burden, costs, income, demographics, "
                 "and housing)", fontsize=10, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    plots.save(fig, "map_typology.png")
    print("Saved typology tables and map")
