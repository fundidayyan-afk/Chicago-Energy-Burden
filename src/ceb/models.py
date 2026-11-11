"""Phase 2 regression models: OLS, spatial lag/error/Durbin, and MGWR.

Research Questions 2-4. Each function returns plain pandas objects so the
scripts can write tables and the paper can quote numbers directly.
"""
import numpy as np
import pandas as pd
import spreg
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor

from . import config

XVARS = ["ln_income", "pct_black", "pct_hispanic", "pct_pre1950", "pct_renter", "pct_multifam5"]
LABELS = {
    "CONSTANT": "Constant",
    "ln_income": "ln(median household income)",
    "pct_black": "% Black",
    "pct_hispanic": "% Hispanic",
    "pct_pre1950": "% housing built before 1950",
    "pct_renter": "% renter-occupied",
    "pct_multifam5": "% units in 5+ unit buildings",
    "W_dep_var": "rho (spatial lag)",
    "lambda": "lambda (spatial error)",
}


def design(gdf, outcome, xvars=XVARS):
    """y and X arrays with rows in the same order as gdf (no silent drops)."""
    cols = [outcome] + list(xvars)
    if gdf[cols].isna().any().any():
        bad = gdf[cols].isna().any(axis=1).sum()
        raise ValueError(f"{bad} rows have missing values in {cols}; filter the sample first")
    return gdf[[outcome]].to_numpy(float), gdf[list(xvars)].to_numpy(float)


def vif_table(gdf, xvars=XVARS):
    X = np.column_stack([np.ones(len(gdf)), gdf[list(xvars)].to_numpy(float)])
    return pd.Series([variance_inflation_factor(X, i + 1) for i in range(len(xvars))],
                     index=list(xvars), name="VIF")


def tidy(model, label):
    """Coefficient table from any spreg model."""
    names = list(model.name_x)
    if hasattr(model, "lam") and "lambda" not in names:
        names = names + ["lambda"]
    stat = getattr(model, "z_stat", None) or getattr(model, "t_stat")
    return pd.DataFrame({
        "model": label,
        "term": names,
        "coef": np.ravel(model.betas)[:len(names)],
        "se": np.ravel(model.std_err)[:len(names)],
        "stat": [s[0] for s in stat][:len(names)],
        "p": [s[1] for s in stat][:len(names)],
    })


def ols(gdf, outcome, w, xvars=XVARS):
    """OLS with spatial diagnostics, plus White-robust standard errors."""
    y, X = design(gdf, outcome, xvars)
    base = spreg.OLS(y, X, w=w, spat_diag=True, moran=True, white_test=True,
                     name_y=outcome, name_x=list(xvars))
    robust = spreg.OLS(y, X, robust="white", name_y=outcome, name_x=list(xvars))
    diag = {
        "n": base.n, "adj_r2": base.ar2, "aic": base.aic, "logll": base.logll,
        "breusch_pagan": base.breusch_pagan["bp"], "breusch_pagan_p": base.breusch_pagan["pvalue"],
        "moran_resid_I": base.moran_res[0], "moran_resid_p": base.moran_res[2],
        "lm_lag": base.lm_lag[0], "lm_lag_p": base.lm_lag[1],
        "lm_error": base.lm_error[0], "lm_error_p": base.lm_error[1],
        "rlm_lag": base.rlm_lag[0], "rlm_lag_p": base.rlm_lag[1],
        "rlm_error": base.rlm_error[0], "rlm_error_p": base.rlm_error[1],
        "condition_number": float(np.linalg.cond(X / np.linalg.norm(X, axis=0))),
    }
    table = tidy(base, f"OLS: {outcome}")
    table["se_robust"] = np.ravel(robust.std_err)
    table["p_robust"] = [s[1] for s in robust.t_stat]
    return base, table, diag


def choose_spatial(diag, alpha=config.ALPHA):
    """Anselin's (2005) decision rule using the (robust) LM tests.

    Returns 'none', 'lag', or 'error', plus a sentence for the methods section.
    """
    lag, err = diag["lm_lag_p"] < alpha, diag["lm_error_p"] < alpha
    if not lag and not err:
        return "none", "Neither LM test rejects, so OLS is retained."
    if lag and not err:
        return "lag", "Only the LM-lag test is significant, so a spatial lag model is used."
    if err and not lag:
        return "error", "Only the LM-error test is significant, so a spatial error model is used."
    rlag, rerr = diag["rlm_lag_p"] < alpha, diag["rlm_error_p"] < alpha
    if rlag and not rerr:
        return "lag", "Both LM tests reject; only robust LM-lag remains significant, so a spatial lag model is used."
    if rerr and not rlag:
        return "error", "Both LM tests reject; only robust LM-error remains significant, so a spatial error model is used."
    kind = "lag" if diag["rlm_lag"] >= diag["rlm_error"] else "error"
    return kind, (f"Both robust LM tests reject; the larger statistic favors a spatial {kind} model, "
                  "and the spatial Durbin model is reported as a check.")


def spatial_model(gdf, outcome, w, kind, xvars=XVARS):
    y, X = design(gdf, outcome, xvars)
    common = dict(name_y=outcome, name_x=list(xvars))
    if kind == "lag":
        m = spreg.ML_Lag(y, X, w=w, **common)
    elif kind == "error":
        m = spreg.ML_Error(y, X, w=w, **common)
    elif kind == "durbin":
        m = spreg.ML_Lag(y, X, w=w, slx_lags=1, **common)
    else:
        raise ValueError(kind)
    return m, tidy(m, f"{kind.title()}: {outcome}")


def lag_impacts(model, w, xvars=XVARS, draws=2000, seed=config.SEED):
    """Direct, indirect (spillover), and total effects for a spatial lag model.

    In a lag model a coefficient is not a marginal effect: a change in one
    tract moves its neighbors' burden, which feeds back. With row-standardized
    W, the average direct effect is beta * mean(diag((I - rho W)^-1)) and the
    total is beta / (1 - rho) (LeSage & Pace, 2009). The diagonal mean comes
    from W's eigenvalues, so simulation over parameter draws is cheap.
    """
    eig = np.real(np.linalg.eigvals(w.full()[0]))
    k = len(xvars)
    b = np.ravel(model.betas)              # [const, x1..xk, rho]
    vm = np.asarray(model.vm)

    def effects(beta, rho):
        d = np.mean(1.0 / (1.0 - rho * eig))
        total = beta / (1.0 - rho)
        return beta * d, total - beta * d, total

    rng = np.random.default_rng(seed)
    sims = rng.multivariate_normal(b, vm, size=draws)
    sims = sims[np.abs(sims[:, -1]) < 1]
    rows = []
    for j, name in enumerate(xvars, start=1):
        point = effects(b[j], b[-1])
        sim = np.array([effects(s[j], s[-1]) for s in sims])
        for i, kind in enumerate(("direct", "indirect", "total")):
            lo, hi = np.percentile(sim[:, i], [2.5, 97.5])
            z = point[i] / sim[:, i].std()
            rows.append({"term": name, "effect": kind, "estimate": point[i], "ci_low": lo, "ci_high": hi,
                         "p": 2 * (1 - stats.norm.cdf(abs(z)))})
    return pd.DataFrame(rows)


def mgwr_fit(gdf, outcome, xvars=XVARS):
    """Multiscale GWR on standardized variables, bandwidths chosen by AICc.

    Returns tract-level coefficients (local R-squared is not defined for MGWR) (with nonsignificant ones set to NaN
    after the mgwr package's multiple-testing correction), bandwidths, and
    a fit summary.
    """
    from mgwr.gwr import MGWR
    from mgwr.sel_bw import Sel_BW

    pts = gdf.geometry.to_crs(config.PROJECTED_CRS).representative_point()
    coords = np.column_stack([pts.x, pts.y])
    y, X = design(gdf, outcome, xvars)
    y = (y - y.mean()) / y.std()
    X = (X - X.mean(axis=0)) / X.std(axis=0)

    selector = Sel_BW(coords, y, X, multi=True)
    selector.search(multi_bw_min=[2])
    res = MGWR(coords, y, X, selector).fit()

    terms = ["CONSTANT"] + list(xvars)
    params = pd.DataFrame(res.params, columns=terms, index=gdf["GEOID"].to_numpy())
    filtered = pd.DataFrame(res.filter_tvals(), columns=terms, index=params.index)
    sig = params.where(filtered != 0)
    local_cn = res.local_collinearity()[0]
    summary = {
        "aicc": res.aicc, "r2": res.R2, "adj_r2": res.adj_R2,
        "bandwidths": dict(zip(terms, np.ravel(selector.bw[0]).tolist())),
        "max_local_condition_number": float(np.max(local_cn)),
        "share_tracts_cn_over_30": float(np.mean(np.max(local_cn, axis=1) > 30)),
    }
    return params, sig, summary
