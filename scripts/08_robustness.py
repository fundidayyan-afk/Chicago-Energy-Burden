"""Step 8: robustness checks for the main spatial models.

Main specification: spatial error model, queen weights, ACS 2018-2022,
all tracts in the main sample. Each check changes one thing:
  A. k-nearest-neighbor weights (k = 6) instead of queen contiguity
  B. drop tracts where an ACS covariate is unreliable (CV > 0.40)
  C. ACS 2020-2024 covariates instead of 2018-2022
  D. outcome = share of households above 6% / 10% (fractional logit,
     plus a spatial error model on the share as a spatial check)
  E. an independent burden measure from ACS utility-cost tables,
     compared with LEAD

Outputs in output/tables/: robustness_<outcome>.csv (wide comparison),
robustness_long.csv, threshold_models.csv, validation.json; and
output/figures/validation_scatter.png.
"""
import json

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ceb import acs, config, geo, models, robustness

OUTCOMES = {"burden_pct": "Energy burden (%)", "ln_avg_energy_cost": "ln(average energy cost)"}
MAIN = "error"   # chosen by the LM tests in 05_models.py for both outcomes


def fit(gdf, outcome, weights="queen", kind=MAIN):
    w = geo.weights(gdf, weights)
    _, t = models.spatial_model(gdf, outcome, w, kind)
    return t


if __name__ == "__main__":
    full = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    full["ln_avg_energy_cost"] = np.log(full["avg_energy_cost"])
    main = full[full["in_main_sample"].astype(bool)].reset_index(drop=True)
    print(f"Main sample: {len(main)} tracts")

    # C. ACS 2020-2024 covariates, same tracts and outcomes
    acs24_path = config.RAW / f"acs5_{config.ACS_YEAR_CHECK}_tracts.csv"
    acs24 = None
    if acs24_path.exists():
        cov24 = acs.build_covariates(acs.load_acs(acs24_path))
        keep = ["GEOID"] + models.XVARS
        acs24 = (main.drop(columns=models.XVARS).merge(cov24[keep], on="GEOID", how="left")
                     .dropna(subset=models.XVARS).reset_index(drop=True))
        print(f"ACS 2020-2024 sample: {len(acs24)} tracts")

    reliable = main[~main["flag_acs_unreliable"].astype(bool)].reset_index(drop=True)
    print(f"Reliable-ACS sample: {len(reliable)} tracts")

    all_long, notes = [], ["# Robustness checks", ""]
    for outcome, label in OUTCOMES.items():
        specs = {
            "Main (queen, ACS 2018-22)": fit(main, outcome),
            "A. KNN-6 weights": fit(main, outcome, "knn"),
            f"B. Reliable ACS only (n={len(reliable)})": fit(reliable, outcome),
        }
        if acs24 is not None:
            specs[f"C. ACS 2020-24 (n={len(acs24)})"] = fit(acs24, outcome)
        long, wide = robustness.compare(specs)
        long.insert(0, "outcome", outcome)
        all_long.append(long)
        wide.index = [models.LABELS.get(i, i) for i in wide.index]
        wide.to_csv(config.TABLES / f"robustness_{outcome}.csv")
        print(f"\n{label}\n{wide.to_string()}")
        n_stable = (wide["stable across specs"] == "yes").sum()
        notes.append(f"- {label}: {n_stable} of {len(wide)} coefficients keep the same sign and "
                     f"significance in every specification.")
    pd.concat(all_long).to_csv(config.TABLES / "robustness_long.csv", index=False)

    # D. Threshold outcomes
    thr = []
    for outcome in ("share_high", "share_severe"):
        fl = robustness.fractional_logit(main, outcome)
        thr.append(fl)
        _, sp = models.spatial_model(main, outcome, geo.weights(main, "queen"), "error")
        sp["model"] = f"Spatial error (linear): {outcome}"
        thr.append(sp)
    thr = pd.concat(thr, ignore_index=True)
    thr["label"] = thr["term"].map(models.LABELS).fillna(thr["term"])
    thr.to_csv(config.TABLES / "threshold_models.csv", index=False)
    print("\nThreshold outcomes (fractional logit, average marginal effects)")
    print(thr[thr["model"].str.startswith("Fractional")][["model", "term", "ame", "ame_se", "p"]]
          .round(4).to_string(index=False))

    # E. Independent ACS burden measure
    from ceb.download import download_acs_utility
    validation = {}
    util_path = config.RAW / f"acs5_{config.ACS_YEAR}_utility_tracts.csv"
    labels_path = config.RAW / f"acs5_{config.ACS_YEAR}_utility_labels.json"
    try:
        if not util_path.exists():
            download_acs_utility()
        util = pd.read_csv(util_path, dtype={"GEOID": str})
        labels = json.loads(labels_path.read_text())
        acsb = robustness.acs_burden(util, labels, main[["GEOID", "med_hh_income"]])
        print("\nACS cost bins used (column: assumed monthly $):")
        for t, b in acsb.attrs["bins"].items():
            print(f"  {t}: " + ", ".join(f"{labels[c].split('!!')[-1]} -> {m:.0f}" for c, m in b.items()))
        v = main[["GEOID", "burden_pct", "avg_energy_cost"]].merge(acsb, on="GEOID")
        validation = {
            "burden": robustness.agreement(v["burden_pct"], v["acs_burden_pct"]),
            "annual_cost": robustness.agreement(v["avg_energy_cost"], v["acs_annual_cost"]),
            "lead_mean_burden": float(v["burden_pct"].mean()),
            "acs_mean_burden": float(v["acs_burden_pct"].mean()),
            "note": ("ACS costs cover only households that pay electricity/gas bills directly and use "
                     "bin midpoints (top bin x1.25); the denominator is median household income. "
                     "Expect strong rank agreement, not equal levels."),
        }
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
        for ax, (x, y, t) in zip(axes, [("acs_burden_pct", "burden_pct", "Energy burden (%)"),
                                        ("acs_annual_cost", "avg_energy_cost", "Annual energy cost ($)")]):
            ax.scatter(v[x], v[y], s=6, alpha=0.5, color="#2166ac")
            r = validation["burden" if "burden" in x else "annual_cost"]["spearman"]
            ax.set_xlabel(f"ACS-based ({'paying households' if 'cost' in x else 'utility bills / median income'})")
            ax.set_ylabel("LEAD")
            ax.set_title(f"{t}\nSpearman rho = {r:.2f}")
        fig.tight_layout()
        fig.savefig(config.FIGURES / "validation_scatter.png", dpi=200, bbox_inches="tight")
        print("\nValidation:", json.dumps(validation, indent=2))
    except Exception as e:  # validation must not block the other results
        validation = {"error": f"{type(e).__name__}: {e}"}
        print(f"\nValidation skipped: {validation['error']}")
    (config.TABLES / "validation.json").write_text(json.dumps(validation, indent=2))

    (config.TABLES / "robustness_notes.md").write_text("\n".join(notes) + "\n")
    print("\n".join(notes))
