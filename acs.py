"""Build tract-level explanatory variables from ACS counts, with reliability flags.

Shares are built from counts, and their margins of error use the Census
Bureau's formula for derived proportions (ACS Handbook, ch. 8). The
coefficient of variation (CV = SE / estimate) flags estimates too noisy to
trust; the robustness checks re-run models without those tracts.
"""
import numpy as np
import pandas as pd

from .download import ACS_VARS

Z90 = 1.645
# ACS uses large negative sentinels for "not available" (e.g. -666666666).
SENTINEL = -100_000_000


def load_acs(path):
    raw = pd.read_csv(path, dtype={"GEOID": str})
    out = pd.DataFrame({"GEOID": raw["GEOID"]})
    for code, name in ACS_VARS.items():
        e = pd.to_numeric(raw[f"{code}E"], errors="coerce")
        m = pd.to_numeric(raw[f"{code}M"], errors="coerce")
        out[name] = e.where(e > SENTINEL)
        out[f"{name}_moe"] = m.where(m > SENTINEL).abs()
    return out


def _sum_moe(*moes):
    return np.sqrt(sum(np.square(m) for m in moes))


def _prop(num, num_moe, den, den_moe):
    """Proportion and its MOE (falls back to the ratio formula when needed)."""
    p = num / den
    inside = num_moe**2 - (p**2) * den_moe**2
    ratio = num_moe**2 + (p**2) * den_moe**2
    moe = np.sqrt(np.where(inside >= 0, inside, ratio)) / den
    return p, moe


def build_covariates(acs):
    a = acs
    v = pd.DataFrame({"GEOID": a["GEOID"]})

    v["med_hh_income"] = a["med_hh_income"]
    v["ln_income"] = np.log(a["med_hh_income"])
    v["cv_income"] = (a["med_hh_income_moe"] / Z90) / a["med_hh_income"]

    def share(name, num_cols, den_col):
        num = sum(a[c] for c in num_cols)
        num_moe = _sum_moe(*[a[f"{c}_moe"] for c in num_cols])
        p, moe = _prop(num, num_moe, a[den_col], a[f"{den_col}_moe"])
        v[name] = 100 * p
        v[f"cv_{name}"] = np.where(p > 0, (moe / Z90) / p, np.nan)

    share("pct_black", ["pop_nh_black"], "pop_total")
    share("pct_hispanic", ["pop_hispanic"], "pop_total")
    share("pct_white", ["pop_nh_white"], "pop_total")
    share("pct_renter", ["renter_units"], "occ_units")
    share("pct_pre1950", ["units_1940_49", "units_pre1940"], "units_total_yb")
    share("pct_multifam5", ["units_5_9", "units_10_19", "units_20_49", "units_50plus"], "units_total_str")
    share("pct_gas_heat", ["heat_utility_gas"], "heat_total")
    share("pct_elec_heat", ["heat_electric"], "heat_total")
    share("pct_below_poverty", ["pov_under_050", "pov_050_099"], "pov_universe")
    v["med_year_built"] = a["med_year_built"]
    v["pop_total"] = a["pop_total"]
    return v


def flag_unreliable(cov, threshold, columns=("cv_income", "cv_pct_renter", "cv_pct_pre1950", "cv_pct_multifam5")):
    cv = cov[list(columns)]
    return (cv > threshold).any(axis=1)
