"""Write the companion notebooks in notebooks/ (one per analysis step).

Each notebook explains its step, recomputes the quick parts live from the
processed data (so a reader can change something and rerun), and shows the
pipeline's saved results for slow parts such as MGWR. GitHub Actions executes
them after every pipeline run, so the copies on GitHub show current outputs.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"
NB.mkdir(exist_ok=True)

SETUP = """import json, warnings
import numpy as np, pandas as pd, geopandas as gpd
from IPython.display import Image, Markdown, display
from ceb import config
warnings.filterwarnings("ignore")
pd.set_option("display.precision", 4)
T, F = config.TABLES, config.FIGURES
gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
sample = gdf[gdf["in_main_sample"].astype(bool)].reset_index(drop=True)
print(f"{len(gdf)} tracts mostly inside Chicago; {len(sample)} in the analysis sample")"""


def md(s):
    return nbf.v4.new_markdown_cell(s.strip())


def code(s):
    return nbf.v4.new_code_cell(s.strip())


def write(name, title, intro, cells):
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.cells = [md(f"# {title}\n\n{intro.strip()}\n\n_Part of the Chicago Energy Burden project "
                   "(James Rocco Quantitative Data Research Scholarship, Lake Forest College). Run the pipeline "
                   "scripts first, or read the executed copy on GitHub._"), code(SETUP)] + cells
    nbf.write(nb, NB / name)
    print(f"wrote notebooks/{name}")


write("01_data_and_validation.ipynb", "1. Data and validation",
      """Energy burden comes from the DOE LEAD Tool (2022), explanatory variables from the 2018-2022 ACS.
This notebook shows how the sample was built, what each tract looks like, and how the LEAD-based
measure compares with ACEEE's published Chicago figures and with an independent ACS-based measure.
Script: `scripts/02_build.py`.""", [
    md("## Sample construction\nEvery tract that was flagged or dropped, and why."),
    code('display(Markdown((T / "exclusions.md").read_text()))'),
    md("## Descriptive statistics (analysis sample)"),
    code('''cols = ["burden_pct", "li_burden_pct", "share_high", "share_severe", "avg_energy_cost", "med_hh_income",
        "pct_black", "pct_hispanic", "pct_pre1950", "pct_renter", "pct_multifam5", "households"]
sample[cols].describe().T[["mean", "std", "min", "50%", "max"]].round(2)'''),
    md("## Benchmark check against ACEEE\nACEEE reports median household burdens; the citywide figure here is total "
       "spending over total income, so this is a sanity check, not an exact comparison."),
    code('''city = 100 * sample["energy_total"].sum() / sample["income_total"].sum()
li = sample.dropna(subset=["li_burden_pct"])
li_city = 100 * li["li_energy_total"].sum() / li["li_income_total"].sum()
pd.DataFrame({"This study (LEAD 2022)": [city, li_city],
              "ACEEE 2024, Chicago": [config.ACEEE_2024_CHICAGO["all_households_median"],
                                      config.ACEEE_2024_CHICAGO["low_income_median"]]},
             index=["All households (%)", "Low-income households (%)"]).round(2)'''),
    md("## Independent check: ACS utility-cost tables\nIf LEAD's modeling were driving the geography, an independent "
       "measure would rank tracts differently. It does not."),
    code('''v = json.loads((T / "validation.json").read_text())
display(pd.DataFrame({k: v[k] for k in ("burden", "annual_cost") if k in v}).T.round(3))
if (F / "validation_scatter.png").exists(): display(Image(F / "validation_scatter.png", width=800))'''),
])

write("02_exploratory_spatial_analysis.ipynb", "2. Where is burden concentrated? (RQ1)",
      """Global Moran's I tests whether burden is spatially random; local Moran's I (LISA) finds the
clusters, with a false discovery rate correction so hundreds of tests do not overstate significance.
Script: `scripts/03_explore.py`. The statistics below are recomputed live (999 permutations; the
pipeline uses 9,999).""", [
    code('''from esda import Moran, Moran_Local, fdr
from ceb import geo
w = geo.weights(sample, "queen")
y = sample["burden_pct"].to_numpy()
m = Moran(y, w, permutations=999)
print(f"Global Moran's I = {m.I:.3f} (expected under randomness {m.EI:.4f}), pseudo p = {m.p_sim:.4f}")'''),
    code('''lm = Moran_Local(y, w, permutations=999, seed=config.SEED)
cut = fdr(lm.p_sim, 0.05)
labels = pd.Series(lm.q).map({1: "High-High", 2: "Low-High", 3: "Low-Low", 4: "High-Low"})
labels[lm.p_sim > cut] = "Not significant"
labels.value_counts()'''),
    md("## Maps (from the pipeline)"),
    code('display(Image(F / "map_burden.png", width=520)); display(Image(F / "map_lisa.png", width=520))'),
])

write("03_regression_models.ipynb", "3. What explains burden? (RQ2 and RQ3)",
      """OLS first, with diagnostics; then Lagrange Multiplier tests and likelihood ratio tests to choose
among the spatial error, spatial lag, and spatial Durbin models. The cost model (log average energy
bill) separates the cost side of burden from the income side. Script: `scripts/05_models.py`.""", [
    code('''from ceb import geo, models
w = geo.weights(sample, "queen")
ols, table, diag = models.ols(sample, "burden_pct", w)
display(table[["term", "coef", "se", "p", "se_robust", "p_robust"]].round(4))
pd.Series({k: diag[k] for k in ["adj_r2", "breusch_pagan_p", "moran_resid_I", "moran_resid_p",
                                "lm_lag_p", "lm_error_p", "rlm_lag_p", "rlm_error_p"]}).round(4)'''),
    code('models.vif_table(sample).round(2)'),
    md("## Choosing the spatial model\nLikelihood ratio tests: the spatial error model is the Durbin model with the "
       "common factor restriction; the lag model is the Durbin model without neighbors' covariates."),
    code('''lr = pd.read_csv(T / "lr_tests.csv")
lr[["spec", "lm_choice", "lr_common_factor", "p_common_factor", "lr_durbin_vs_lag", "p_durbin_vs_lag",
    "aic_error", "aic_lag", "aic_durbin", "choice"]].round(4)'''),
    md("## Effects from the main models\nFor the Durbin model: direct = a tract's own characteristics, "
       "indirect = spillover from neighbors, total = both."),
    code('''for spec in ["burden_pct", "ln_avg_energy_cost"]:
    d = pd.read_csv(T / f"impacts_{spec}.csv")
    display(Markdown(f"**{spec}**"))
    display(d.pivot(index="label", columns="effect", values="estimate").round(4))'''),
    code('display(Image(F / "effects_burden_costs.png", width=900)); display(Image(F / "effects_fuels.png", width=900))'),
])

write("04_mgwr.ipynb", "4. Does it differ across the city? (RQ4)",
      """Multiscale GWR lets each variable work at its own spatial scale. A bandwidth near the full sample means
a relationship is the same citywide; a small one means it changes from one neighborhood to the next.
Script: `scripts/06_mgwr.py` (the fit takes a few minutes, so saved results are shown).""", [
    code('''s = json.loads((T / "mgwr_summary.json").read_text())
display(pd.Series(s["bandwidths"], name="bandwidth (nearest tracts)").to_frame())
display(pd.Series(s["share_tracts_significant"], name="share of tracts significant").round(3).to_frame())
{k: s[k] for k in ["adj_r2", "aicc", "max_local_condition_number", "moran_resid_I"]}'''),
    md("## Model comparison (energy burden, original units)"),
    code('pd.read_csv(T / "model_comparison_burden.csv").round(3)'),
    code('''for v in ["ln_income", "pct_black", "pct_hispanic", "pct_pre1950", "pct_renter", "pct_multifam5"]:
    display(Image(F / f"mgwr_{v}.png", width=430))'''),
])

write("05_robustness.ipynb", "5. Robustness checks",
      """Each check changes one thing: neighbor definition, dropping unreliable ACS tracts, newer ACS data,
threshold outcomes (shares above 6% and 10%), and fuel-specific models. Script: `scripts/08_robustness.py`.""", [
    code('display(Markdown((T / "robustness_notes.md").read_text()))'),
    code('''for f in sorted(T.glob("robustness_*.csv")):
    if f.stem == "robustness_long": continue
    display(Markdown(f"**{f.stem}**")); display(pd.read_csv(f, index_col=0))'''),
    md("## Measurement error (ACS margins of error) and heteroskedasticity\nScript: `scripts/13_uncertainty.py`. "
       "Each draw resamples every ACS input within its margin of error and refits the spatial Durbin model; "
       "draws are combined with Rubin's rules."),
    code('''display(Markdown((T / "uncertainty_summary.md").read_text()))
for o in ["burden_pct", "ln_avg_energy_cost"]:
    display(Markdown(f"**{o}**"))
    display(pd.read_csv(T / f"moe_combined_{o}.csv")[["label", "effect", "original_estimate", "moe_estimate",
            "moe_se", "moe_p", "moe_share_variance_from_measurement"]].round(4))
    r = pd.read_csv(T / f"robust_estimators_{o}.csv")
    display(r[r["effect"] == "direct"].pivot(index="label", columns="estimator", values="estimate").round(4))'''),
    md("## Threshold outcomes (fractional logit, average marginal effects)"),
    code('''thr = pd.read_csv(T / "threshold_models.csv")
thr[thr["model"].str.startswith("Fractional") & (thr["term"] != "CONSTANT")][["model", "label", "ame", "ame_se", "p"]].round(4)'''),
])

write("07_typology.ipynb", "7. Neighborhood typology",
      """k-means clustering on nine standardized characteristics groups tracts into types, so places can be
described as a whole rather than one variable at a time. Script: `scripts/14_typology.py`.""", [
    code('''from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
feats = ["burden_pct", "ln_income", "pct_black", "pct_hispanic", "pct_pre1950", "pct_renter", "pct_multifam5", "pct_elec_heat"]
s = sample.assign(ln_avg_energy_cost=np.log(sample["avg_energy_cost"])).dropna(subset=feats)
X = StandardScaler().fit_transform(s[feats + ["ln_avg_energy_cost"]])
pd.DataFrame({"k": range(3, 9), "silhouette": [silhouette_score(X, KMeans(k, n_init=20, random_state=1).fit_predict(X)) for k in range(3, 9)]}).round(3)'''),
    code('pd.read_csv(T / "typology_profiles.csv").round(2)'),
    code('pd.read_csv(T / "typology_by_cluster.csv")'),
    code('display(Image(F / "map_typology.png", width=900))'),
])

write("06_policy_and_context.ipynb", "6. Policy analysis and building context",
      """Which rule for choosing tracts reaches the most severely burdened households, and how much would a
cost cut in the priority tracts help? Counts use LEAD household groups. The last section uses the
City's Energy Benchmarking data on large multifamily buildings as context.
Scripts: `scripts/10_policy.py`, `scripts/11_figures.py`, `scripts/12_benchmarking.py`.""", [
    code('display(Markdown((T / "policy_summary.md").read_text()))'),
    code('pd.read_csv(T / "policy_targeting.csv").round(3)'),
    code('pd.read_csv(T / "policy_scenarios.csv").round(2)'),
    code('display(Image(F / "map_priority.png", width=560))'),
    code('pd.read_csv(T / "priority_by_community_area.csv").head(15)'),
    md("## Energy Benchmarking: large multifamily buildings"),
    code('''b = json.loads((T / "benchmarking_summary.json").read_text())
display(pd.Series({k: v for k, v in b.items() if not isinstance(v, dict)}).to_frame("value"))
for f in ["benchmarking_by_cluster.csv", "benchmarking_by_era.csv"]:
    if (T / f).exists(): display(pd.read_csv(T / f).round(1))'''),
])
