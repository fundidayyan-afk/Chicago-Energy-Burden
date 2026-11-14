# Where Energy Bills Hurt Most: Household Energy Burden Across Chicago

**Dayyan Lutshaka Fundi** · James Rocco Quantitative Data Research Scholarship, Lake Forest College
Advisors: Dr. Andrew Gard (primary), Dr. Sugata Banerji (technical)

Energy burden is the share of household income spent on home energy. This project maps and models it across Chicago's census tracts to answer four questions:

1. **Where is burden concentrated?** Global Moran's I and LISA hotspot maps.
2. **What explains it?** OLS, then a spatial lag or spatial error model chosen by Lagrange Multiplier tests.
3. **High bills or low incomes?** A companion model of energy costs, separating the cost side from the income side.
4. **Does it differ across the city?** Multiscale Geographically Weighted Regression (MGWR).

> **Status:** All analysis phases run on real data: data build and validation, clustering, spatial regression with formal model selection, fuel-specific models, MGWR, robustness checks, policy analysis, and building-level context.

## Results

**[See the latest results →](output/RESULTS.md)** · **[Interactive map →](https://dayyan-website.vercel.app/energy-burden.html)** (maps, cluster statistics, and regression tables, rebuilt automatically every time the code changes).

The whole analysis runs on GitHub's servers through [GitHub Actions](.github/workflows/pipeline.yml). To rerun it by hand: **Actions** tab → **Run analysis pipeline** → **Run workflow**. Each run saves its log to [`output/run_log.txt`](output/run_log.txt).

## Data

| Source | What it gives | Role |
|---|---|---|
| [DOE LEAD Tool, 2022 update](https://doi.org/10.25984/2504170) | Households, income, and electricity, gas, and other fuel spending by tract and income group | Outcome (energy burden) |
| [ACS 5-year, 2018-2022](https://www.census.gov/data/developers/data-sets/acs-5year.html) | Income, race and ethnicity, tenure, housing age and type, heating fuel, with margins of error | Explanatory variables |
| [Census TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | 2020 tract and city boundaries | Geography |
| ACEEE Chicago estimates (2020, 2024) | Published burden medians | Validation benchmark |

All sources are public. Raw files are not committed; `scripts/01_download.py` recreates them.

## How to reproduce

```bash
git clone https://github.com/fundidayyan-afk/chicago-energy-burden.git
cd chicago-energy-burden
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt && pip install -e .

python scripts/01_download.py           # raw data -> data/raw/
python scripts/02_build.py              # analysis dataset + exclusion log
python scripts/03_explore.py            # maps, Moran's I, LISA clusters
python scripts/04_preliminary_summary.py
python scripts/05_models.py            # OLS, LM + LR tests, spatial error/lag/Durbin, fuel models
python scripts/06_mgwr.py              # MGWR and the final model comparison (a few minutes)
python scripts/08_robustness.py        # weights, reliable tracts, ACS 2020-24, thresholds, ACS validation
python scripts/10_policy.py            # targeting rules and cost-cut scenarios (household groups)
python scripts/11_figures.py           # coefficient plots and the priority-tract map
python scripts/12_benchmarking.py      # Chicago Energy Benchmarking context
python scripts/09_web_data.py          # data for the interactive map
python scripts/07_report.py            # output/RESULTS.md
python scripts/build_notebooks.py      # notebooks/ (then run them in Jupyter)
```

A free [Census API key](https://api.census.gov/data/key_signup.html) is optional but recommended: set it as the environment variable `CENSUS_API_KEY`.

To test the pipeline without downloading anything, run it on a synthetic city in a scratch copy of the repo:

```bash
pytest
python tests/make_synthetic_data.py && python scripts/02_build.py && python scripts/03_explore.py
```

## Repository layout

```
src/ceb/          reusable code: config, download, LEAD and ACS processing, geography, spatial stats
scripts/          numbered steps, run in order
notebooks/        one notebook per step, executed by GitHub Actions after every run
tests/            unit tests and a synthetic-data generator
data/processed/   analysis-ready tract file (committed once final)
output/figures/   maps and plots
output/tables/    regression tables, cluster lists, sample construction log
```

## Method notes

- **Burden** is total energy spending divided by total income in each tract (a ratio of sums). The shares of households above 6% and 10% are computed from LEAD's income-group averages, so they understate how many households cross each line; they are reported as lower bounds.
- **Tracts in Chicago** are those with at least half of their land area inside the city boundary.
- **Unstable tracts** (fewer than 100 households, or missing covariates) are excluded and listed in `output/tables/exclusions.md`. ACS estimates with a coefficient of variation above 0.40 are flagged and dropped in a robustness check.
- **LISA significance** uses 9,999 permutations and a 5% false discovery rate, so hotspots are not overstated across hundreds of tracts.
- **Model choice** uses Lagrange Multiplier tests (Anselin et al., 1996) and then likelihood ratio tests that nest the spatial error (common factor) and spatial lag models inside the spatial Durbin model (Elhorst, 2010); the reasoning is written out in `output/tables/model_selection.md`. For Durbin and lag models, direct, spillover, and total effects are reported with simulated 95% intervals (LeSage & Pace, 2009).
- **Policy counts** (targeting rules, cost-cut scenarios) use LEAD household groups, so a household is counted above a burden line when its group's average is above it.
- **MGWR** uses standardized variables and AICc bandwidths; local coefficients are mapped only where significant after the package's multiple-testing correction.
- Results describe **neighborhoods, not individual households**.

## License

Code: MIT. Data remain under their original public licenses.
