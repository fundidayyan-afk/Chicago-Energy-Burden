"""Step 11: coefficient plots with 95% intervals, and the priority-tract map.

Effects come from the main models chosen in 05_models.py. Variables differ
in scale (a doubling of income moves burden far more than 10 points of any
share), so each effect is shown for a one-standard-deviation increase in that
variable across the 768 tracts; the size of that step is printed in each
label. Cost outcomes are logs, so their effects are shown as percent changes
in average bills, 100 x (exp(effect) - 1).

Outputs in output/figures/: effects_burden_costs.png, effects_fuels.png,
map_priority.png; output/tables/priority_tracts.csv gains community areas.
"""
import json

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D

from ceb import config, models, plots

DIRECT, TOTAL = "#2a78d6", "#eb6834"      # validated categorical slots 1-2 (dataviz palette)
INK, MUTED, GRID = "#1f1f1e", "#6b6b66", "#e4e3df"
ORDER = ["ln_income", "pct_black", "pct_hispanic", "pct_pre1950", "pct_renter", "pct_multifam5"]
NAMES = {"ln_income": "Median income", "pct_black": "% Black", "pct_hispanic": "% Hispanic",
         "pct_pre1950": "% built before 1950", "pct_renter": "% renter-occupied",
         "pct_multifam5": "% in 5+ unit buildings", "pct_elec_heat": "% heated by electricity"}
SD = {}
NICE = {}


def set_scales(gdf):
    """One-standard-deviation steps and the labels that state them."""
    for t in NAMES:
        if t in gdf:
            SD[t] = float(gdf[t].std())
            step = (f"x{np.exp(SD[t]):.2f}" if t == "ln_income" else f"+{SD[t]:.0f} pts")
            NICE[t] = f"{NAMES[t]} ({step})"


def scaled(spec):
    d = pd.read_csv(config.TABLES / f"impacts_{spec}.csv")
    k = d["term"].map(SD).to_numpy()
    for c in ("estimate", "ci_low", "ci_high"):
        d[c] = d[c] * k
        if spec.startswith("ln_"):
            d[c] = 100 * (np.exp(d[c]) - 1)
    return d


def forest(ax, d, title, unit):
    terms = [t for t in ORDER if t in set(d["term"])]
    effects = [e for e in ("direct", "total") if e in set(d["effect"])]
    offs = {"direct": 0.17, "total": -0.17} if len(effects) == 2 else {effects[0]: 0}
    for i, t in enumerate(terms):
        y = len(terms) - 1 - i
        if i % 2 == 0:
            ax.axhspan(y - 0.5, y + 0.5, color="#f4f3f0", zorder=0, lw=0)
        for e in effects:
            r = d[(d["term"] == t) & (d["effect"] == e)].iloc[0]
            col, mk = (DIRECT, "o") if e == "direct" else (TOTAL, "D")
            ax.plot([r.ci_low, r.ci_high], [y + offs[e]] * 2, color=col, lw=2, solid_capstyle="round", zorder=2)
            ax.plot(r.estimate, y + offs[e], mk, ms=7, color=col, mec="white", mew=1.2, zorder=3)
    ax.axvline(0, color=MUTED, lw=1, zorder=1)
    ax.set_yticks(range(len(terms)))
    ax.set_yticklabels([NICE[t] for t in reversed(terms)], fontsize=8.5, color=INK)
    ax.set_ylim(-0.6, len(terms) - 0.4)
    ax.set_xlabel(unit, fontsize=8.5, color=MUTED)
    ax.set_title(title, fontsize=10.5, color=INK, loc="left", fontweight="bold")
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)


def legend(fig, kind):
    handles = [Line2D([], [], color=DIRECT, marker="o", lw=2, ms=7, mec="white", label="Direct effect (own tract)"),
               Line2D([], [], color=TOTAL, marker="D", lw=2, ms=7, mec="white",
                      label="Total effect (own tract + spillover from neighbors)")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.01, 0.99), ncol=2, frameon=False, fontsize=8.5)
    fig.text(0.012, 0.915, f"Effect of a one-standard-deviation increase in each variable (step shown in "
                           f"brackets). Spatial {kind.capitalize()} model, 768 Chicago tracts; lines are 95% intervals.",
             ha="left", va="top", fontsize=7.5, color=MUTED)


if __name__ == "__main__":
    main = json.loads((config.TABLES / "main_models.json").read_text())
    sample = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    set_scales(sample[sample["in_main_sample"].astype(bool)])

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    forest(axes[0], scaled("burden_pct"), "Energy burden", "Change in burden (percentage points)")
    forest(axes[1], scaled("ln_avg_energy_cost"), "Average energy bill", "Change in average yearly bill (%)")
    legend(fig, main["burden_pct"]["model"])
    fig.tight_layout(rect=(0, 0.02, 1, 0.88))
    plots.save(fig, "effects_burden_costs.png", "Model estimates; LEAD 2022 and ACS 2018-2022.")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    forest(axes[0], scaled("elec_burden_pct"), "Electricity burden", "Change in burden (percentage points)")
    forest(axes[1], scaled("gas_burden_pct"), "Natural gas burden", "Change in burden (percentage points)")
    legend(fig, main["elec_burden_pct"]["model"])
    fig.tight_layout(rect=(0, 0.02, 1, 0.88))
    plots.save(fig, "effects_fuels.png", "Model estimates; LEAD 2022 and ACS 2018-2022.")

    # Priority-tract map: the high-burden clusters, shaded by burden, with neighborhood names
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    gdf = gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True)
    lisa = pd.read_csv(config.TABLES / "lisa_clusters.csv", dtype={"GEOID": str})
    gdf = gdf.merge(lisa[["GEOID", "cluster"]], on="GEOID", how="left")
    gdf["area"] = plots.area_of_tracts(gdf)
    pri = gdf[gdf["cluster"] == "High-High"]
    fig, ax = plots.base_map(gdf)
    gdf.plot(ax=ax, color="#ecebe7", edgecolor="white", linewidth=0.2, zorder=1)
    reds = ListedColormap(plt.cm.Reds(np.linspace(0.35, 1.0, 256)))   # skip near-white so every class shows
    pri.plot(ax=ax, column="burden_pct", cmap=reds, scheme="Quantiles", k=4, legend=True, zorder=2,
             edgecolor="white", linewidth=0.2,
             legend_kwds={"title": "Burden in priority tracts (%)", "loc": "lower left", "fontsize": 7,
                          "title_fontsize": 7.5})
    counts = pri["area"].value_counts()
    plots.add_context(ax, labels=list(counts[counts >= 5].index) if pri["area"].notna().any() else None)
    ax.set_title(f"Priority tracts: {len(pri)} tracts in significant high-burden clusters\n"
                 f"{pri['households'].sum():,.0f} households", fontsize=10)
    plots.save(fig, "map_priority.png")

    path = config.TABLES / "priority_tracts.csv"
    if path.exists():
        t = pd.read_csv(path, dtype={"GEOID": str}).drop(columns="community_area", errors="ignore")
        t = t.merge(gdf[["GEOID", "area"]].rename(columns={"area": "community_area"}), on="GEOID", how="left")
        t.to_csv(path, index=False)
        summary = (t.groupby("community_area").agg(tracts=("GEOID", "size"), households=("households", "sum"))
                    .sort_values("households", ascending=False))
        summary.to_csv(config.TABLES / "priority_by_community_area.csv")
        print("Priority tracts by community area (top 15)\n" + summary.head(15).to_string())
    print("Saved effect plots and priority map")
