"""How much do the results depend on ACS sampling error and on constant-variance assumptions?

1. Measurement error (ACS margins of error). The explanatory variables are
   survey estimates. Each simulation draw replaces every ACS count and the
   median income with a value drawn from a normal distribution centered on the
   published estimate, with standard error = MOE / 1.645 (ACS MOEs are 90%
   intervals), rebuilds the covariates, and refits the main model. The draws
   are combined with Rubin's rules: the total variance of an effect is the
   average model variance plus (1 + 1/M) times the variance of the estimates
   across draws (Rubin, 1987). This treats measurement error the way multiple
   imputation treats missing data.

2. Heteroskedasticity. The Breusch-Pagan test rejects constant variance. The
   main spatial Durbin model is re-estimated by spatial two-stage least squares
   with White-robust standard errors, and by GMM with heteroskedasticity-robust
   inference for spatially correlated errors (Kelejian & Prucha, 2010;
   Arraiz et al., 2010), and the effects are compared.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import spreg

from . import acs, config
from .download import ACS_VARS
from .models import XVARS, design, durbin_impacts, spatial_model

Z90 = 1.645


def perturb_acs(acs_raw, rng):
    """One draw of the ACS table: estimates resampled within their margins of error."""
    d = acs_raw.copy()
    for name in ACS_VARS.values():
        est, moe = d[name], d[f"{name}_moe"].fillna(0)
        draw = est + rng.normal(0, 1, len(d)) * (moe / Z90)
        floor = 2500 if name == "med_hh_income" else 0
        d[name] = draw.clip(lower=floor).where(est.notna())
    return d


def covariates_from(acs_raw):
    cov = acs.build_covariates(acs_raw)
    for c in XVARS:
        if c.startswith("pct_"):
            cov[c] = cov[c].clip(0, 100)
    return cov[["GEOID"] + XVARS]


def rubin(estimates, variances):
    """Combine M estimates of one quantity (Rubin, 1987)."""
    q, u = np.asarray(estimates), np.asarray(variances)
    m = len(q)
    qbar, ubar, b = q.mean(), u.mean(), q.var(ddof=1)
    t = ubar + (1 + 1 / m) * b
    se = np.sqrt(t)
    r = (1 + 1 / m) * b / max(ubar, 1e-300)
    df = (m - 1) * (1 + 1 / max(r, 1e-12)) ** 2
    from scipy import stats
    p = 2 * stats.t.sf(abs(qbar / se), df)
    return {"estimate": qbar, "se": se, "p": p, "share_variance_from_measurement": (1 + 1 / m) * b / t,
            "draw_low": np.percentile(q, 2.5), "draw_high": np.percentile(q, 97.5)}


def moe_simulation(sample, acs_raw, w, outcome, draws, seed=config.SEED, impact_draws=500):
    """Refit the spatial Durbin model on `draws` resampled covariate sets."""
    rng = np.random.default_rng(seed)
    base = sample.drop(columns=XVARS)
    rows = []
    for i in range(draws):
        cov = covariates_from(perturb_acs(acs_raw, rng))
        g = base.merge(cov, on="GEOID", how="left")
        if g[XVARS].isna().any().any():          # keep tract order fixed for W; fill rare gaps with the original
            g[XVARS] = g[XVARS].fillna(sample[XVARS])
        m, _ = spatial_model(g, outcome, w, "durbin")
        imp = durbin_impacts(m, w, draws=impact_draws, seed=seed + i)
        imp["draw"] = i
        rows.append(imp[["draw", "term", "effect", "estimate", "se"]])
    return pd.concat(rows, ignore_index=True)


def combine(sim, original):
    """Rubin-combined effects next to the original estimates."""
    out = []
    for (term, effect), g in sim.groupby(["term", "effect"], sort=False):
        r = rubin(g["estimate"], g["se"] ** 2)
        o = original[(original["term"] == term) & (original["effect"] == effect)].iloc[0]
        out.append({"term": term, "effect": effect, "original_estimate": o["estimate"], "original_p": o["p"],
                    **{f"moe_{k}": v for k, v in r.items()},
                    "share_draws_significant": float(((g["estimate"] / g["se"]).abs() > 1.96).mean())})
    return pd.DataFrame(out)


def hac_kernel(sample, k=12):
    """Adaptive triangular kernel over the k nearest tracts, for spatial HAC standard errors."""
    import libpysal
    pts = sample.copy()
    pts["geometry"] = sample.geometry.representative_point()
    return libpysal.weights.Kernel.from_dataframe(pts, fixed=False, k=k, function="triangular",
                                                  diagonal=True, use_index=False)


def robust_checks(sample, outcome, w, xvars=XVARS):
    """Effects under estimators that do not assume constant error variance.

    - ML spatial Durbin (the main model, for reference)
    - Spatial Durbin by S2SLS with White SEs, and by GMM robust to heteroskedasticity
      (Kelejian & Prucha, 2010; Arraiz et al., 2010). Their direct effects are
      reliable; rho is only weakly identified by the spatial instruments once WX is
      in the model, so their total effects are reported with that caveat.
    - SLX (OLS with neighbors' covariates) with spatial HAC standard errors
      (Kelejian & Prucha, 2007): direct = beta, spillover = theta, total = beta + theta,
      identified without rho (Halleck Vega & Elhorst, 2015).
    - Spatial error model by GMM, robust to heteroskedasticity: direct effects.
    """
    y, X = design(sample, outcome, xvars)
    k = len(xvars)
    out, notes = [], {}

    def durbin(name, b, vm, rho_note=None):
        imp = durbin_impacts(SimpleNamespace(betas=b, vm=vm), w, xvars)
        imp.insert(0, "estimator", name)
        imp["rho"] = b[-1]
        imp["rho_se"] = float(np.sqrt(vm[-1, -1]))
        out.append(imp)

    ml, _ = spatial_model(sample, outcome, w, "durbin", xvars)
    durbin("ML spatial Durbin (main)", np.ravel(ml.betas), np.asarray(ml.vm))
    s2 = spreg.GM_Lag(y, X, w=w, slx_lags=1, w_lags=2, robust="white", name_x=list(xvars), name_y=outcome)
    durbin("S2SLS spatial Durbin, White SEs", np.ravel(s2.betas), np.asarray(s2.vm))
    het = spreg.GM_Combo_Het(y, X, w=w, slx_lags=1, w_lags=2, name_x=list(xvars), name_y=outcome)
    p = 2 * k + 2                                  # const, x, Wx, rho (lambda dropped)
    durbin("GMM spatial Durbin, heteroskedasticity-robust", np.ravel(het.betas)[:p], np.asarray(het.vm)[:p, :p])

    slx = spreg.OLS(y, X, w=w, slx_lags=1, robust="hac", gwk=hac_kernel(sample), name_x=list(xvars), name_y=outcome)
    b, vm = np.ravel(slx.betas), np.asarray(slx.vm)
    from scipy import stats
    for j, t in enumerate(xvars):
        i_b, i_t = 1 + j, 1 + k + j
        for eff, est, var in [("direct", b[i_b], vm[i_b, i_b]), ("indirect", b[i_t], vm[i_t, i_t]),
                              ("total", b[i_b] + b[i_t], vm[i_b, i_b] + vm[i_t, i_t] + 2 * vm[i_b, i_t])]:
            se = float(np.sqrt(var))
            out.append(pd.DataFrame([{"estimator": "SLX, spatial HAC SEs", "term": t, "effect": eff,
                                      "estimate": est, "se": se, "ci_low": est - 1.96 * se, "ci_high": est + 1.96 * se,
                                      "p": 2 * stats.norm.sf(abs(est / se))}]))
    eh = spreg.GM_Error_Het(y, X, w=w, name_x=list(xvars), name_y=outcome)
    b, vm = np.ravel(eh.betas), np.asarray(eh.vm)
    for j, t in enumerate(xvars):
        est, se = b[1 + j], float(np.sqrt(vm[1 + j, 1 + j]))
        out.append(pd.DataFrame([{"estimator": "GMM spatial error, heteroskedasticity-robust", "term": t,
                                  "effect": "direct", "estimate": est, "se": se, "ci_low": est - 1.96 * se,
                                  "ci_high": est + 1.96 * se, "p": 2 * stats.norm.sf(abs(est / se))}]))
    return pd.concat(out, ignore_index=True)
