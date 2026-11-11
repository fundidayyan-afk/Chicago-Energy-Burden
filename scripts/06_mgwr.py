"""Step 6: Multiscale GWR (Research Question 4). Takes a few minutes.

Outputs:
  output/tables/mgwr_summary.json        bandwidths, fit, local collinearity check
  output/tables/mgwr_coefficients.csv    tract-level standardized coefficients
  output/figures/mgwr_<variable>.png     maps of significant local coefficients
"""
import json

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

from ceb import config, models

if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    gdf = gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True)

    params, sig, summary = models.mgwr_fit(gdf, "burden_pct")
    params.to_csv(config.TABLES / "mgwr_coefficients.csv", index_label="GEOID")
    (config.TABLES / "mgwr_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    if summary["share_tracts_cn_over_30"] > 0.05:
        print("Warning: local condition numbers above 30 in more than 5% of tracts; "
              "interpret local coefficients with care (see Fotheringham & Oshan, 2016).")

    for var in models.XVARS:
        g = gdf[["GEOID", "geometry"]].merge(sig[[var]], left_on="GEOID", right_index=True)
        vals = g[var].dropna()
        fig, ax = plt.subplots(figsize=(6, 8))
        gdf.plot(ax=ax, color="#e8e8e8", edgecolor="white", linewidth=0.2)
        if len(vals):
            lim = max(abs(vals.min()), abs(vals.max()), 1e-9)
            g.dropna().plot(column=var, ax=ax, cmap="RdBu_r", edgecolor="white", linewidth=0.2,
                            norm=TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim), legend=True,
                            legend_kwds={"shrink": 0.5, "label": "Standardized local coefficient"})
        bw = summary["bandwidths"][var]
        ax.set_title(f"{models.LABELS[var]}\nMGWR bandwidth = {bw:.0f} neighbors; grey = not significant")
        ax.set_axis_off()
        fig.savefig(config.FIGURES / f"mgwr_{var}.png", dpi=200, bbox_inches="tight")
        plt.close(fig)
    print("Saved MGWR tables and maps")
