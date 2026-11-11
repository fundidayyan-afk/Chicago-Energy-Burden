"""Step 5: OLS, model selection, and spatial regression (Research Questions 2 and 3).

Two outcomes are modeled with the same covariates:
  burden_pct          energy burden (% of income)
  ln_avg_energy_cost  log of average annual energy spending per household
Comparing them shows whether a gap in burden comes from higher bills or
from lower incomes.

Outputs in output/tables/: vif.csv, ols_diagnostics.csv, coefficients.csv,
lag_impacts.csv (if a lag model is chosen), model_comparison.csv,
model_selection.md.
"""
import geopandas as gpd
import numpy as np
import pandas as pd
from esda import Moran

from ceb import config, geo, models

OUTCOMES = {"burden_pct": "Energy burden (%)", "ln_avg_energy_cost": "ln(average energy cost)"}

if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    gdf = gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True)
    gdf["ln_avg_energy_cost"] = np.log(gdf["avg_energy_cost"])
    w = geo.weights(gdf, "queen")

    vif = models.vif_table(gdf)
    vif.to_csv(config.TABLES / "vif.csv")
    print("VIF\n", vif.round(2).to_string())

    coef_tables, diags, comparison, notes = [], {}, [], ["# Model selection", ""]
    for outcome, label in OUTCOMES.items():
        base, table, diag = models.ols(gdf, outcome, w)
        coef_tables.append(table)
        diags[outcome] = diag
        comparison.append({"outcome": outcome, "model": "OLS", "aic": diag["aic"], "logll": diag["logll"],
                           "moran_resid_I": diag["moran_resid_I"]})

        kind, why = models.choose_spatial(diag)
        notes += [f"## {label}", "",
                  f"- Residual Moran's I = {diag['moran_resid_I']:.3f} (p = {diag['moran_resid_p']:.4f})",
                  f"- LM lag = {diag['lm_lag']:.2f} (p = {diag['lm_lag_p']:.4f}); "
                  f"LM error = {diag['lm_error']:.2f} (p = {diag['lm_error_p']:.4f})",
                  f"- Robust LM lag = {diag['rlm_lag']:.2f} (p = {diag['rlm_lag_p']:.4f}); "
                  f"robust LM error = {diag['rlm_error']:.2f} (p = {diag['rlm_error_p']:.4f})",
                  f"- Breusch-Pagan = {diag['breusch_pagan']:.1f} (p = {diag['breusch_pagan_p']:.4f})",
                  f"- **Decision:** {why}", ""]
        print(f"\n{label}: {why}")

        fits = ["lag", "error", "durbin"] if kind == "none" else [kind, "durbin"]
        for k in fits:
            m, t = models.spatial_model(gdf, outcome, w, k)
            coef_tables.append(t)
            # Error models: check the spatially filtered residuals. Lag models: plain residuals.
            resid = m.e_filtered if k == "error" else m.u
            comparison.append({"outcome": outcome, "model": k, "aic": m.aic, "logll": m.logll,
                               "moran_resid_I": float(Moran(np.ravel(resid), w, permutations=0).I)})
            if k == "lag":
                imp = models.lag_impacts(m, w)
                imp.insert(0, "outcome", outcome)
                imp.to_csv(config.TABLES / f"lag_impacts_{outcome}.csv", index=False)

    coefs = pd.concat(coef_tables, ignore_index=True)
    coefs["label"] = coefs["term"].map(models.LABELS).fillna(coefs["term"])
    coefs.to_csv(config.TABLES / "coefficients.csv", index=False)
    pd.DataFrame(comparison).to_csv(config.TABLES / "model_comparison.csv", index=False)
    pd.DataFrame(diags).T.to_csv(config.TABLES / "ols_diagnostics.csv")
    (config.TABLES / "model_selection.md").write_text("\n".join(notes))
    print("\n", pd.DataFrame(comparison).round(3).to_string(index=False))
    print("\nSaved tables to output/tables")
