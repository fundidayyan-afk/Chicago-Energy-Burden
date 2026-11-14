"""Robustness checks and an independent ACS-based burden measure."""
import re

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .models import XVARS


# --- ACS utility-cost measure -------------------------------------------------

def bin_midpoint(label, top_multiplier=1.25):
    """Dollar midpoint for an ACS cost-bin label, or None if it is not a dollar bin.

    'Less than $50' -> 25; '$50 to $99' -> 75; '$250 or more' -> 250 * 1.25
    (a common convention for open-ended top bins; reported as an assumption).
    """
    leaf = label.split("!!")[-1]
    nums = [float(n.replace(",", "")) for n in re.findall(r"\$([\d,]+)", leaf)]
    if not nums:
        return None
    low = leaf.lower()
    if "less than" in low:
        return nums[0] / 2
    if "or more" in low:
        return nums[0] * top_multiplier
    if len(nums) == 2:
        return (nums[0] + nums[1] + 1) / 2
    return None


def acs_monthly_cost(df, labels, table):
    """Mean monthly cost among households that pay the bill directly."""
    cols = {c: bin_midpoint(labels[c]) for c in df.columns if c.startswith(table) and c in labels}
    bins = {c: m for c, m in cols.items() if m is not None}
    if not bins:
        raise ValueError(f"No dollar bins found for {table}; labels: {[labels[c] for c in cols]}")
    n = df[list(bins)].apply(pd.to_numeric, errors="coerce").clip(lower=0)
    payers = n.sum(axis=1)
    mean = (n * pd.Series(bins)).sum(axis=1) / payers.replace(0, np.nan)
    return mean, payers, bins


def acs_burden(util, labels, income):
    """Annual electricity + gas cost (ACS, paying households) / median household income."""
    elec, elec_n, elec_bins = acs_monthly_cost(util, labels, "B25132")
    gas, gas_n, gas_bins = acs_monthly_cost(util, labels, "B25133")
    annual = 12 * (elec.fillna(0) + gas.fillna(0))
    out = pd.DataFrame({"GEOID": util["GEOID"].astype(str), "acs_elec_month": elec, "acs_gas_month": gas,
                        "acs_annual_cost": annual})
    out = out.merge(income, on="GEOID", how="left")
    out["acs_burden_pct"] = 100 * out["acs_annual_cost"] / out["med_hh_income"]
    out.attrs["bins"] = {"B25132": elec_bins, "B25133": gas_bins}
    return out.drop(columns=["med_hh_income"])


def agreement(a, b, top=0.2):
    """Correlations and overlap of the top quintile between two tract measures."""
    d = pd.DataFrame({"a": a, "b": b}).dropna()
    qa, qb = d["a"] >= d["a"].quantile(1 - top), d["b"] >= d["b"].quantile(1 - top)
    return {"n": int(len(d)), "pearson": float(d["a"].corr(d["b"])),
            "spearman": float(d["a"].corr(d["b"], method="spearman")),
            "top_quintile_overlap": float((qa & qb).sum() / qa.sum())}


# --- Threshold outcomes ------------------------------------------------------------

def fractional_logit(gdf, outcome, xvars=XVARS):
    """Papke-Wooldridge fractional logit with robust SEs and average marginal effects."""
    y = gdf[outcome].clip(0, 1).to_numpy(float)
    X = sm.add_constant(gdf[list(xvars)].to_numpy(float))
    res = sm.GLM(y, X, family=sm.families.Binomial()).fit(cov_type="HC1")
    p = res.predict(X)
    scale = np.mean(p * (1 - p))
    terms = ["CONSTANT"] + list(xvars)
    out = pd.DataFrame({"model": f"Fractional logit: {outcome}", "term": terms,
                        "coef": res.params, "se": res.bse, "p": res.pvalues})
    out["ame"] = np.where(out["term"] == "CONSTANT", np.nan, out["coef"] * scale)
    out["ame_se"] = np.where(out["term"] == "CONSTANT", np.nan, out["se"] * scale)
    return out.reset_index(drop=True)


# --- Coefficient comparison --------------------------------------------------------

def compare(tables, xvars=XVARS):
    """Wide table: one row per variable, one column per specification."""
    rows = []
    for spec, t in tables.items():
        t = t[t["term"].isin(xvars)]
        for r in t.itertuples():
            stars = "***" if r.p < 0.001 else "**" if r.p < 0.01 else "*" if r.p < 0.05 else ""
            rows.append({"spec": spec, "term": r.term, "coef": r.coef, "se": r.se, "p": r.p,
                         "cell": f"{r.coef:.4f}{stars} ({r.se:.4f})"})
    long = pd.DataFrame(rows)
    wide = long.pivot(index="term", columns="spec", values="cell").reindex(xvars)[list(tables)]
    main = list(tables)[0]
    base = long[long["spec"] == main].set_index("term")
    stable = []
    for v in xvars:
        sub = long[long["term"] == v]
        b = base.loc[v]
        same_sign = (np.sign(sub["coef"]) == np.sign(b["coef"])).all()
        same_sig = ((sub["p"] < 0.05) == (b["p"] < 0.05)).all()
        stable.append("yes" if same_sign and same_sig else
                      "sign stable, significance changes" if same_sign else "NO: sign changes")
    wide["stable across specs"] = stable
    return long, wide
