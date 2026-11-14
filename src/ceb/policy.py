"""Policy analysis on LEAD household groups (cohorts), not tract averages.

Two questions from the proposal:
  1. Targeting: if a program can serve a fixed number of tracts (or a fixed
     number of households), which rule for choosing tracts reaches the most
     households with high (>6%) and severe (>10%) energy burden?
  2. Scenario: if efficiency upgrades cut energy costs in the priority tracts,
     how far does burden fall and how many households drop below 6%?

Counts above a line use cohort averages (a household is counted when its
group's average burden is above the line), so they are approximations;
see the method notes in the README.
"""
import numpy as np
import pandas as pd

from . import config


def cohort_counts(coh, tracts=None):
    """Households, high- and severe-burden households, and totals for a set of tracts."""
    c = coh if tracts is None else coh[coh["tract"].isin(tracts)]
    hh = c["units"].sum()
    return {
        "households": hh,
        "hh_above_6": c.loc[c["cohort_burden"] > config.BURDEN_HIGH, "units"].sum(),
        "hh_above_10": c.loc[c["cohort_burden"] > config.BURDEN_SEVERE, "units"].sum(),
        "low_income_hh": c.loc[c["low_income"], "units"].sum(),
        "burden_pct": 100 * c["energy"].sum() / c["income"].sum() if hh else np.nan,
        "energy_total": c["energy"].sum(),
    }


def select(tr, order_col, ascending, n_tracts=None, n_households=None):
    """Tracts chosen by a ranking rule, for a fixed number of tracts or households."""
    ranked = tr.sort_values(order_col, ascending=ascending)
    if n_tracts is not None:
        return list(ranked["GEOID"].head(n_tracts))
    cum = ranked["households"].cumsum()
    k = int(np.searchsorted(cum.to_numpy(), n_households) + 1)
    return list(ranked["GEOID"].head(k))


def targeting(tr, coh, cluster_ids, rules):
    """Compare rules at equal tracts and at equal households served.

    tr: tract table with GEOID, households and the ranking columns.
    rules: {name: (column, ascending)}; the LISA cluster rule is added here.
    """
    city = cohort_counts(coh)
    n_tr = len(cluster_ids)
    n_hh = tr.loc[tr["GEOID"].isin(cluster_ids), "households"].sum()
    rows = []
    for budget, kwargs in [("Same number of tracts", {"n_tracts": n_tr}),
                           ("Same number of households", {"n_households": n_hh})]:
        chosen = {"High-burden clusters (LISA)": list(cluster_ids)}
        for name, (col, asc) in rules.items():
            chosen[name] = select(tr, col, asc, **kwargs)
        for name, ids in chosen.items():
            c = cohort_counts(coh, ids)
            rows.append({
                "budget": budget, "rule": name, "tracts": len(ids), "households": c["households"],
                "hh_above_10": c["hh_above_10"], "share_of_city_above_10": c["hh_above_10"] / city["hh_above_10"],
                "hh_above_6": c["hh_above_6"], "share_of_city_above_6": c["hh_above_6"] / city["hh_above_6"],
                "precision_above_10": c["hh_above_10"] / c["households"],
                "low_income_hh": c["low_income_hh"],
                "overlap_with_clusters": len(set(ids) & set(cluster_ids)),
            })
    out = pd.DataFrame(rows)
    out.attrs["city"] = city
    return out


def cut_costs(coh, tracts, cut, low_income_only=False):
    """Cohorts after cutting energy costs by `cut` (0.2 = 20%) in the chosen tracts."""
    c = coh.copy()
    c["energy"] = c["energy"].astype(float)
    mask = c["tract"].isin(tracts)
    if low_income_only:
        mask &= c["low_income"]
    c.loc[mask, "energy"] = c.loc[mask, "energy"] * (1 - cut)
    c["cohort_burden"] = 100 * c["energy"] / c["income"]
    return c


def scenarios(coh, tracts, cuts=(0.10, 0.20, 0.30)):
    """Burden and threshold counts before and after cost cuts in the priority tracts."""
    base_area = cohort_counts(coh, tracts)
    base_city = cohort_counts(coh)
    base_li = cohort_counts(coh[coh["low_income"]], tracts)
    rows = []
    for li_only in (False, True):
        for cut in cuts:
            after = cut_costs(coh, tracts, cut, li_only)
            a_area, a_city = cohort_counts(after, tracts), cohort_counts(after)
            a_li = cohort_counts(after[after["low_income"]], tracts)
            targeted = after["tract"].isin(tracts) & (after["low_income"] if li_only else True)
            served = coh.loc[targeted, "units"].sum()
            savings = base_area["energy_total"] - a_area["energy_total"]
            rows.append({
                "who": "Low-income households (<80% AMI) only" if li_only else "All households",
                "cost_cut": cut,
                "households_served": served,
                "burden_before": base_area["burden_pct"], "burden_after": a_area["burden_pct"],
                "li_burden_before": base_li["burden_pct"], "li_burden_after": a_li["burden_pct"],
                "above_6_before": base_area["hh_above_6"], "above_6_after": a_area["hh_above_6"],
                "dropped_below_6": base_area["hh_above_6"] - a_area["hh_above_6"],
                "above_10_before": base_area["hh_above_10"], "above_10_after": a_area["hh_above_10"],
                "dropped_below_10": base_area["hh_above_10"] - a_area["hh_above_10"],
                "city_above_6_before": base_city["hh_above_6"], "city_above_6_after": a_city["hh_above_6"],
                "annual_savings_total": savings,
                "annual_savings_per_served_hh": savings / served if served else np.nan,
            })
    return pd.DataFrame(rows)
