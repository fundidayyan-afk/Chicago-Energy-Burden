"""Step 5: OLS, model selection, and spatial regression (Research Questions 2 and 3).

Outcomes, all with the same six covariates:
  burden_pct            energy burden (% of income)
  ln_avg_energy_cost    log average yearly energy spending per household (cost side)
  elec_burden_pct       electricity burden, and ln_avg_elec_cost (its cost side)
  gas_burden_pct        natural gas burden, and ln_avg_gas_cost (its cost side)
The fuel-specific burden models are also run with the share of homes heated
by electricity added, since heating fuel shifts spending between the two.

Model choice for each outcome, in two stages:
  1. OLS diagnostics and (robust) Lagrange Multiplier tests (Anselin et al., 1996)
  2. Likelihood ratio tests nesting the spatial error and spatial lag models
     inside the spatial Durbin model (Elhorst, 2010). The model these tests
     select is the main model; its effects are what the paper interprets.

Outputs in output/tables/: vif.csv, ols_diagnostics.csv, coefficients.csv,
model_comparison.csv, lr_tests.csv, main_models.json, impacts_<outcome>.csv,
model_selection.md.
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
from esda import Moran

from ceb import config, geo, models

OUTCOMES = {
    "burden_pct": "Energy burden (%)",
    "ln_avg_energy_cost": "ln(average energy cost)",
    "elec_burden_pct": "Electricity burden (%)",
    "ln_avg_elec_cost": "ln(average electricity cost)",
    "gas_burden_pct": "Gas burden (%)",
    "ln_avg_gas_cost": "ln(average gas cost)",
}
HEAT_VARIANT = {"elec_burden_pct": "Electricity burden (%), heating fuel control",
                "gas_burden_pct": "Gas burden (%), heating fuel control"}
HEAT_XVARS = models.XVARS + ["pct_elec_heat"]


def add_outcomes(gdf):
    hh = gdf["households"]
    gdf["ln_avg_energy_cost"] = np.log(gdf["avg_energy_cost"])
    gdf["ln_avg_elec_cost"] = np.log((gdf["elec_total"] / hh).where(gdf["elec_total"] > 0))
    gdf["ln_avg_gas_cost"] = np.log((gdf["gas_total"] / hh).where(gdf["gas_total"] > 0))
    return gdf


def label_terms(table, outcome):
    def lab(t):
        if t in models.LABELS:
            return models.LABELS[t]
        if t == f"W_{outcome}":
            return "rho (spatial lag)"
        if t.startswith("W_") and t[2:] in models.LABELS:
            return "Neighbors' " + models.LABELS[t[2:]]
        return t
    table["label"] = table["term"].map(lab)
    return table


def residual_moran(m, kind, w):
    resid = m.e_filtered if kind == "error" else m.u
    return float(Moran(np.ravel(resid), w, permutations=0).I)


def run(gdf, w, outcome, label, xvars, tag, store):
    sub = gdf.dropna(subset=[outcome] + list(xvars)).reset_index(drop=True)
    ww = w if len(sub) == len(gdf) else geo.weights(sub, "queen")
    base, table, diag = models.ols(sub, outcome, ww, xvars)
    store["coefs"].append(label_terms(table.assign(spec=tag), outcome))
    store["diags"][tag] = {**diag, "outcome": outcome}
    store["comparison"].append({"spec": tag, "outcome": outcome, "model": "OLS", "aic": diag["aic"],
                                "logll": diag["logll"], "moran_resid_I": diag["moran_resid_I"], "n": len(sub)})
    lm_kind, lm_why = models.choose_spatial(diag)
    sel, fits = models.select_spatial_model(sub, outcome, ww, xvars)
    sel["spec"], sel["lm_choice"], sel["n"] = tag, lm_kind, len(sub)
    store["lr"].append(sel)
    for kind, (m, t) in fits.items():
        store["coefs"].append(label_terms(t.assign(spec=tag), outcome))
        store["comparison"].append({"spec": tag, "outcome": outcome, "model": kind, "aic": m.aic,
                                    "logll": m.logll, "moran_resid_I": residual_moran(m, kind, ww), "n": len(sub)})
    choice = sel["choice"]
    main = fits[choice][0]
    if choice == "durbin":
        imp = models.durbin_impacts(main, ww, xvars)
    elif choice == "lag":
        imp = models.lag_impacts(main, ww, xvars)
    else:   # error model: the coefficients are the marginal effects
        t = fits["error"][1]
        t = t[t["term"].isin(xvars)]
        imp = pd.DataFrame({"term": t["term"], "effect": "direct", "estimate": t["coef"], "se": t["se"],
                            "ci_low": t["coef"] - 1.96 * t["se"], "ci_high": t["coef"] + 1.96 * t["se"],
                            "p": t["p"]})
    imp.insert(0, "model", choice)
    imp.insert(0, "spec", tag)
    imp["label"] = imp["term"].map(models.LABELS).fillna(imp["term"])
    imp.to_csv(config.TABLES / f"impacts_{tag}.csv", index=False)
    store["main"][tag] = {"outcome": outcome, "model": choice, "label": label, "xvars": list(xvars)}
    store["notes"] += [
        f"## {label}", "",
        f"- n = {len(sub)}; residual Moran's I (OLS) = {diag['moran_resid_I']:.3f} (p = {diag['moran_resid_p']:.4f})",
        f"- LM lag = {diag['lm_lag']:.2f} (p = {diag['lm_lag_p']:.4f}); LM error = {diag['lm_error']:.2f} "
        f"(p = {diag['lm_error_p']:.4f}); robust LM lag = {diag['rlm_lag']:.2f} (p = {diag['rlm_lag_p']:.4f}); "
        f"robust LM error = {diag['rlm_error']:.2f} (p = {diag['rlm_error_p']:.4f})",
        f"- Stage 1 (LM tests): {lm_why}",
        f"- Stage 2 (LR tests): {sel['why']}",
        f"- AIC: error {sel['aic_error']:.1f}, lag {sel['aic_lag']:.1f}, Durbin {sel['aic_durbin']:.1f}",
        f"- **Main model: {choice}**", ""]
    print(f"\n{label}: LM -> {lm_kind}; LR -> {choice}. {sel['why']}")


if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    gdf = add_outcomes(gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True))
    w = geo.weights(gdf, "queen")

    vif = models.vif_table(gdf)
    vif.to_csv(config.TABLES / "vif.csv")
    print("VIF\n", vif.round(2).to_string())

    store = {"coefs": [], "diags": {}, "comparison": [], "lr": [], "main": {},
             "notes": ["# Model selection", ""]}
    for outcome, label in OUTCOMES.items():
        run(gdf, w, outcome, label, models.XVARS, outcome, store)
    for outcome, label in HEAT_VARIANT.items():
        run(gdf, w, outcome, label, HEAT_XVARS, f"{outcome}_heat", store)

    pd.concat(store["coefs"], ignore_index=True).to_csv(config.TABLES / "coefficients.csv", index=False)
    pd.DataFrame(store["comparison"]).to_csv(config.TABLES / "model_comparison.csv", index=False)
    pd.DataFrame(store["lr"]).to_csv(config.TABLES / "lr_tests.csv", index=False)
    pd.DataFrame(store["diags"]).T.to_csv(config.TABLES / "ols_diagnostics.csv")
    (config.TABLES / "main_models.json").write_text(json.dumps(store["main"], indent=2))
    (config.TABLES / "model_selection.md").write_text("\n".join(store["notes"]))
    print("\n", pd.DataFrame(store["lr"])[["spec", "lm_choice", "choice", "lr_common_factor", "p_common_factor",
                                           "lr_durbin_vs_lag", "p_durbin_vs_lag"]].round(4).to_string(index=False))
    print("\nSaved tables to output/tables")
