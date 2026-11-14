"""Step 6: Multiscale GWR (Research Question 4) and the final model comparison.

Outputs:
  output/tables/mgwr_summary.json          bandwidths, fit, local collinearity check
  output/tables/mgwr_coefficients.csv      tract-level standardized coefficients (+ residuals)
  output/tables/mgwr_significant.csv       the same, blank where not significant
  output/tables/model_comparison_burden.csv  OLS, spatial error, lag, Durbin, and MGWR
                                           compared on AIC, log-likelihood, R-squared, and
                                           residual spatial autocorrelation (original units)
  output/figures/mgwr_<variable>.png       maps of significant local coefficients
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
from esda import Moran
from matplotlib.colors import TwoSlopeNorm

from ceb import config, geo, models, plots

OUTCOME = "burden_pct"

if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    gdf = gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True)
    w = geo.weights(gdf, "queen")

    params, sig, summary = models.mgwr_fit(gdf, OUTCOME)
    params.to_csv(config.TABLES / "mgwr_coefficients.csv", index_label="GEOID")
    sig.to_csv(config.TABLES / "mgwr_significant.csv", index_label="GEOID")
    resid_I = float(Moran(params["residual"].to_numpy(), w, permutations=0).I)
    summary["moran_resid_I"] = resid_I
    (config.TABLES / "mgwr_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    if summary["share_tracts_cn_over_30"] > 0.05:
        print("Warning: local condition numbers above 30 in more than 5% of tracts; "
              "interpret local coefficients with care (see Fotheringham & Oshan, 2016).")

    # Model comparison for energy burden, all on the original scale (percentage points)
    y = gdf[OUTCOME].to_numpy(float)
    tss = float(((y - y.mean()) ** 2).sum())
    comp = pd.read_csv(config.TABLES / "model_comparison.csv")
    comp = comp[comp["spec"] == OUTCOME] if "spec" in comp else comp[comp["outcome"] == OUTCOME]
    names = {"OLS": "OLS", "error": "Spatial error", "lag": "Spatial lag", "durbin": "Spatial Durbin"}
    rows = [{"model": names.get(r.model, r.model), "aic": r.aic, "logll": r.logll,
             "moran_resid_I": r.moran_resid_I} for r in comp.itertuples()]
    rss = float((params["residual"] ** 2).sum())
    rows.append({"model": "MGWR", "aic": summary["aic_original_scale"], "logll": summary["logll_original_scale"],
                 "moran_resid_I": resid_I, "pseudo_r2": 1 - rss / tss,
                 "effective_parameters": summary["effective_parameters"]})
    table = pd.DataFrame(rows)
    table["delta_aic"] = table["aic"] - table["aic"].min()
    table.to_csv(config.TABLES / "model_comparison_burden.csv", index=False)
    print("\nModel comparison, energy burden\n" + table.round(3).to_string(index=False))

    for var in models.XVARS:
        g = gdf[["GEOID", "geometry"]].merge(sig[[var]], left_on="GEOID", right_index=True)
        vals = g[var].dropna()
        fig, ax = plots.base_map(gdf, figsize=(6, 8))
        gdf.plot(ax=ax, color="#e8e8e8", edgecolor="white", linewidth=0.2, zorder=1)
        if len(vals):
            lim = max(abs(vals.min()), abs(vals.max()), 1e-9)
            g.dropna().plot(column=var, ax=ax, cmap="RdBu_r", edgecolor="white", linewidth=0.2, zorder=2,
                            norm=TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim), legend=True,
                            legend_kwds={"shrink": 0.5, "label": "Standardized local coefficient"})
        plots.add_context(ax)
        bw = summary["bandwidths"][var]
        share = summary["share_tracts_significant"][var]
        ax.set_title(f"{models.LABELS[var]}\nMGWR bandwidth = {bw:.0f} neighbors; significant in {share:.0%} "
                     f"of tracts (grey = not significant)", fontsize=9)
        plots.save(fig, f"mgwr_{var}.png")
    print("Saved MGWR tables and maps")
