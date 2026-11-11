"""Turn LEAD cohort rows into one row per census tract.

LEAD does not report individual households. Each row is a cohort: the
households in one tract that share an income bracket (and, in some files,
tenure, building type, building age, or heating fuel). For each cohort it
gives the number of households and their total (or average) income and
electricity, gas, and other-fuel spending.

Two tract measures come out of this:

* burden_pct: total energy spending / total income * 100. This is a ratio of
  sums, so it is weighted toward higher-income households, and it is not
  the same statistic as ACEEE's median household burden.
* share_high / share_severe: share of households in cohorts whose average
  burden exceeds 6% / 10%. Because these are cohort averages, households
  inside a cohort who are above the line while the cohort average is
  below it are missed. Treat these shares as lower-bound approximations
  and say so in the paper.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


def find_lead_csv(folder=config.RAW / "lead_il_2022", kind="AMI"):
    """Locate the tract-level cohort file for an income definition (AMI, FPL, SMI)."""
    hits = [p for p in Path(folder).rglob("*.csv")
            if kind.lower() in p.name.lower() and "tract" in p.name.lower()]
    if not hits:
        found = "\n    ".join(sorted(p.name for p in Path(folder).rglob("*.csv")))
        raise FileNotFoundError(f"No {kind} census-tract CSV under {folder}. Files found:\n    {found}")
    return sorted(hits, key=lambda p: len(p.name))[0]


def _match(columns, pattern):
    hits = [c for c in columns if re.search(pattern, c, flags=re.I)]
    return hits[0] if hits else None


def standardize_columns(df):
    """Map LEAD's column names onto stable internal names.

    LEAD has renamed columns between releases, so match by pattern and
    fail loudly, listing the real columns, if something is missing. Check
    the result against the 2022 data dictionary the first time you run it.
    """
    cols = list(df.columns)
    found = {
        "tract": _match(cols, r"^(FIP|GEOID|FIPS)"),
        "income_bracket": _match(cols, r"^(AMI|FPL|SMI)"),
        "units": _match(cols, r"^UNITS$") or _match(cols, r"^UNITS"),
        "income": _match(cols, r"HINCP"),
        "elec": _match(cols, r"ELEP"),
        "gas": _match(cols, r"GASP"),
        "other_fuel": _match(cols, r"FULP"),
    }
    missing = [k for k, v in found.items() if v is None]
    if missing:
        raise KeyError(f"Could not find LEAD columns for {missing}. Columns are: {cols}")
    out = df[list(found.values())].copy()
    out.columns = list(found.keys())
    # Some releases store totals (HINCP*UNITS), others per-household means.
    totals = "*" in found["income"] or "units" in found["income"].lower()
    out.attrs["money_is_total"] = totals
    out["tract"] = out["tract"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(11)
    return out


def is_low_income(bracket):
    """True for brackets entirely at or below 80% of area median income."""
    label = str(bracket)
    if "+" in label or ">" in label:
        return False
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", label)]
    return bool(nums) and max(nums) <= 80


def tract_burden(raw, low_income_rule=is_low_income):
    """Aggregate cohort rows to one row per tract."""
    df = standardize_columns(raw) if "tract" not in raw.columns else raw.copy()
    money = ["income", "elec", "gas", "other_fuel"]
    if not df.attrs.get("money_is_total", True):
        for c in money:
            df[c] = df[c] * df["units"]
    df = df[df["units"] > 0].copy()
    df["energy"] = df[["elec", "gas", "other_fuel"]].sum(axis=1)

    # Cohorts reporting zero or negative income have undefined burden. Drop
    # them and keep a count so the exclusion is documented.
    bad = df["income"] <= 0
    dropped = int(df.loc[bad, "units"].sum())
    df = df[~bad]

    df["cohort_burden"] = 100 * df["energy"] / df["income"]
    df["low_income"] = df["income_bracket"].map(low_income_rule)

    g = df.groupby("tract")
    out = pd.DataFrame({
        "households": g["units"].sum(),
        "income_total": g["income"].sum(),
        "energy_total": g["energy"].sum(),
        "elec_total": g["elec"].sum(),
        "gas_total": g["gas"].sum(),
    })
    out["burden_pct"] = 100 * out["energy_total"] / out["income_total"]
    out["elec_burden_pct"] = 100 * out["elec_total"] / out["income_total"]
    out["gas_burden_pct"] = 100 * out["gas_total"] / out["income_total"]
    out["avg_energy_cost"] = out["energy_total"] / out["households"]
    out["avg_income"] = out["income_total"] / out["households"]
    for name, cut in [("share_high", config.BURDEN_HIGH), ("share_severe", config.BURDEN_SEVERE)]:
        above = df[df["cohort_burden"] > cut].groupby("tract")["units"].sum()
        out[name] = above.reindex(out.index, fill_value=0) / out["households"]

    li = df[df["low_income"]].groupby("tract")[["units", "income", "energy"]].sum()
    out["li_households"] = li["units"].reindex(out.index, fill_value=0)
    out["li_income_total"] = li["income"].reindex(out.index)
    out["li_energy_total"] = li["energy"].reindex(out.index)
    out["li_burden_pct"] = 100 * out["li_energy_total"] / out["li_income_total"]
    out.attrs["households_dropped_nonpositive_income"] = dropped
    return out.reset_index()


def weighted_median(values, weights):
    v, w = np.asarray(values, float), np.asarray(weights, float)
    keep = ~np.isnan(v) & (w > 0)
    v, w = v[keep], w[keep]
    order = np.argsort(v)
    cum = np.cumsum(w[order])
    return float(v[order][np.searchsorted(cum, cum[-1] / 2)])
