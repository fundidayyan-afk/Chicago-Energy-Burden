"""Step 13: measurement-error simulation and heteroskedasticity-robust estimates.

Set MOE_DRAWS (environment variable) to change the number of simulation draws
(default 200; each draw refits the spatial Durbin model for two outcomes).

Outputs in output/tables/: moe_simulation_<outcome>.csv (all draws),
moe_combined_<outcome>.csv (Rubin-combined), robust_estimators_<outcome>.csv,
uncertainty_summary.md.
"""
import os

import geopandas as gpd
import numpy as np
import pandas as pd

from ceb import acs, config, geo, models, uncertainty

OUTCOMES = {"burden_pct": "Energy burden (%)", "ln_avg_energy_cost": "ln(average energy cost)"}
DRAWS = int(os.environ.get("MOE_DRAWS", 200))

if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    sample = gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True)
    sample["ln_avg_energy_cost"] = np.log(sample["avg_energy_cost"])
    w = geo.weights(sample, "queen")
    acs_raw = acs.load_acs(config.RAW / f"acs5_{config.ACS_YEAR}_tracts.csv")
    acs_raw = acs_raw[acs_raw["GEOID"].isin(set(sample["GEOID"]))].reset_index(drop=True)

    lines = ["# Measurement error and heteroskedasticity", "",
             f"Margin-of-error simulation: {DRAWS} draws of every ACS input, spatial Durbin model refit each time, "
             "combined with Rubin's rules.", ""]
    for outcome, label in OUTCOMES.items():
        m0, _ = models.spatial_model(sample, outcome, w, "durbin")     # the simulation refits this model
        original = models.durbin_impacts(m0, w)
        sim = uncertainty.moe_simulation(sample, acs_raw, w, outcome, DRAWS)
        sim.to_csv(config.TABLES / f"moe_simulation_{outcome}.csv", index=False)
        comb = uncertainty.combine(sim, original)
        comb["label"] = comb["term"].map(models.LABELS)
        comb.to_csv(config.TABLES / f"moe_combined_{outcome}.csv", index=False)
        print(f"\n{label}: margin-of-error simulation\n" + comb.round(4).to_string(index=False))

        rob = uncertainty.robust_durbin(sample, outcome, w)
        rob["label"] = rob["term"].map(models.LABELS)
        rob.to_csv(config.TABLES / f"robust_estimators_{outcome}.csv", index=False)
        piv = rob[rob["effect"] == "total"].pivot(index="label", columns="estimator", values="p")
        print(f"\n{label}: total-effect p-values by estimator\n" + piv.round(4).to_string())

        sig_orig = comb["original_p"] < 0.05
        sig_moe = comb["moe_p"] < 0.05
        lost = comb[sig_orig & ~sig_moe]
        tot = rob[rob["effect"] == "total"]
        stable = tot.groupby("term").apply(lambda g: (g["p"] < 0.05).nunique() == 1 and
                                           (g["estimate"] > 0).nunique() == 1, include_groups=False)
        lines += [f"## {label}", "",
                  f"- Effects significant in the main model that stay significant after accounting for ACS "
                  f"measurement error: {int((sig_orig & sig_moe).sum())} of {int(sig_orig.sum())}"
                  + (f" (lost: {', '.join(lost['label'] + ' ' + lost['effect'])})" if len(lost) else "") + ".",
                  f"- Largest share of an effect's variance due to measurement error: "
                  f"{comb['moe_share_variance_from_measurement'].max():.0%} "
                  f"({comb.loc[comb['moe_share_variance_from_measurement'].idxmax(), 'label']}, "
                  f"{comb.loc[comb['moe_share_variance_from_measurement'].idxmax(), 'effect']}).",
                  f"- Total effects with the same sign and significance under ML, S2SLS-White, and GMM-HET: "
                  f"{int(stable.sum())} of {len(stable)}.", ""]
    (config.TABLES / "uncertainty_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
