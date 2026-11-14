# Results: Household Energy Burden Across Chicago

_Generated 2026-11-14 16:59 UTC by the pipeline. Do not edit by hand; rerun the workflow instead._

## 1. Sample

- Tracts with >= 50% of land area in Chicago: 782
- LEAD households dropped for zero/negative cohort income: 150419
- no LEAD record: 3  
  `17031381700, 17031980000, 17031980100`
- fewer than 100 households: 3  
  `17031381700, 17031980000, 17031980100`
- a model covariate is missing: 14  
  `17031839500, 17031080400, 17031351400, 17031681000, 17031380100, 17031381700, 17031611800, 17031980000, 17031260400, 17031570200, 17031671900, 17031980100, 17031611600, 17031550100`
- an ACS covariate has CV > 0.4 (kept; dropped in robustness): 233
- **Main analysis sample: 768 tracts**

## 2. Summary

The LEAD 2022 data cover 782 census tracts that lie mostly within Chicago; after removing tracts with too few households or missing covariates, 768 tracts and about 1,054,210 households remain. Across all of them, households spend 2.1% of income on energy. Tract burden ranges from 0.5% to 10.9% (10th to 90th percentile: 1.1% to 5.8%), and the household-weighted median tract burden is 2.3%. For households below 80% of area median income, the citywide burden is 6.8% and the median tract burden is 7.0%, compared with ACEEE's 2024 estimate of 7.2% for low-income Chicago households (2.2% for all households). About 26% of households live in income groups whose average burden is above 6%, and 15% above 10%. Burden is strongly clustered in space (global Moran's I = 0.83, p < 0.0001), with 177 tracts in significant high-burden clusters after a false discovery rate correction.

Check before using: ACEEE reports medians of household burdens, while the citywide figure above is total spending over total income. The two should be close in direction and size but are not the same statistic, so describe the comparison as a sanity check, not a match.

## 3. Where is burden concentrated? (RQ1)

| Weights | Global Moran's I | p (permutation) |
|---|---|---|
| queen | 0.831 | 0.0001 |
| knn | 0.831 | 0.0001 |

LISA clusters at 5% FDR: {'Not significant': 384, 'Low-Low': 205, 'High-High': 177, 'Low-High': 2}

| Burden | Clusters |
|---|---|
| ![Energy burden map](figures/map_burden.png) | ![LISA cluster map](figures/map_lisa.png) |

## 4. What explains it? (RQ2 and RQ3)

**Variance inflation factors**

|               |   VIF |
|:--------------|------:|
| ln_income     |  3.15 |
| pct_black     |  4.23 |
| pct_hispanic  |  3.01 |
| pct_pre1950   |  1.42 |
| pct_renter    |  2.49 |
| pct_multifam5 |  2.87 |

### Energy burden (%)

- Residual Moran's I = 0.363 (p = 0.0000)
- LM lag = 230.67 (p = 0.0000); LM error = 305.35 (p = 0.0000)
- Robust LM lag = 25.47 (p = 0.0000); robust LM error = 100.15 (p = 0.0000)
- Breusch-Pagan = 247.4 (p = 0.0000)
- **Decision:** Both robust LM tests reject; the larger statistic favors a spatial error model, and the spatial Durbin model is reported as a check.

### ln(average energy cost)

- Residual Moran's I = 0.269 (p = 0.0000)
- LM lag = 77.70 (p = 0.0000); LM error = 167.78 (p = 0.0000)
- Robust LM lag = 7.90 (p = 0.0049); robust LM error = 97.98 (p = 0.0000)
- Breusch-Pagan = 106.4 (p = 0.0000)
- **Decision:** Both robust LM tests reject; the larger statistic favors a spatial error model, and the spatial Durbin model is reported as a check.

**Energy burden (%)**: coefficient (standard error); * p<0.05, ** p<0.01, *** p<0.001

| label                        | OLS               | Error             | Durbin            |
|:-----------------------------|:------------------|:------------------|:------------------|
| Constant                     | 23.993*** (1.083) | 22.358*** (1.094) | 10.223*** (1.652) |
| ln(median household income)  | -1.865*** (0.088) | -1.739*** (0.089) | -1.655*** (0.091) |
| % Black                      | 0.016*** (0.001)  | 0.013*** (0.002)  | 0.005* (0.003)    |
| % Hispanic                   | 0.006*** (0.002)  | 0.007** (0.002)   | 0.006 (0.003)     |
| % housing built before 1950  | 0.002 (0.002)     | 0.006*** (0.002)  | 0.006*** (0.002)  |
| % renter-occupied            | -0.001 (0.002)    | -0.003 (0.002)    | -0.001 (0.002)    |
| % units in 5+ unit buildings | -0.026*** (0.002) | -0.020*** (0.002) | -0.017*** (0.002) |
| lambda (spatial error)       |                   | 0.674*** (0.035)  |                   |
| W_ln_income                  |                   |                   | 0.867*** (0.151)  |
| W_pct_black                  |                   |                   | -0.001 (0.003)    |
| W_pct_hispanic               |                   |                   | -0.005 (0.004)    |
| W_pct_pre1950                |                   |                   | -0.009*** (0.002) |
| W_pct_renter                 |                   |                   | 0.003 (0.003)     |
| W_pct_multifam5              |                   |                   | 0.005 (0.003)     |
| W_burden_pct                 |                   |                   | 0.617*** (0.038)  |

**ln(average energy cost)**: coefficient (standard error); * p<0.05, ** p<0.01, *** p<0.001

| label                        | OLS               | Error             | Durbin            |
|:-----------------------------|:------------------|:------------------|:------------------|
| Constant                     | 6.344*** (0.166)  | 6.624*** (0.176)  | 2.458*** (0.321)  |
| ln(median household income)  | 0.140*** (0.014)  | 0.116*** (0.014)  | 0.128*** (0.015)  |
| % Black                      | 0.003*** (0.000)  | 0.003*** (0.000)  | 0.001** (0.000)   |
| % Hispanic                   | 0.002*** (0.000)  | 0.002*** (0.000)  | 0.002*** (0.000)  |
| % housing built before 1950  | 0.001*** (0.000)  | 0.002*** (0.000)  | 0.001*** (0.000)  |
| % renter-occupied            | -0.001*** (0.000) | -0.003*** (0.000) | -0.002*** (0.000) |
| % units in 5+ unit buildings | -0.009*** (0.000) | -0.008*** (0.000) | -0.007*** (0.000) |
| lambda (spatial error)       |                   | 0.632*** (0.038)  |                   |
| W_ln_income                  |                   |                   | -0.031 (0.023)    |
| W_pct_black                  |                   |                   | 0.001 (0.001)     |
| W_pct_hispanic               |                   |                   | -0.001 (0.001)    |
| W_pct_pre1950                |                   |                   | -0.002*** (0.000) |
| W_pct_renter                 |                   |                   | 0.003*** (0.001)  |
| W_pct_multifam5              |                   |                   | 0.002*** (0.001)  |
| W_ln_avg_energy_cost         |                   |                   | 0.550*** (0.042)  |

**Model comparison**

| outcome            | model   |      aic |    logll |   moran_resid_I |
|:-------------------|:--------|---------:|---------:|----------------:|
| burden_pct         | OLS     |  1782.66 | -884.332 |           0.363 |
| burden_pct         | error   |  1559.11 | -772.554 |          -0.04  |
| burden_pct         | durbin  |  1534.87 | -753.437 |          -0.033 |
| ln_avg_energy_cost | OLS     | -1093.57 |  553.785 |           0.269 |
| ln_avg_energy_cost | error   | -1241.05 |  627.526 |          -0.022 |
| ln_avg_energy_cost | durbin  | -1292.26 |  660.131 |          -0.009 |

## 5. Does it differ across the city? (RQ4)

MGWR adjusted R² = 0.930; AICc = 340.8; max local condition number = 9.0

| Variable | Bandwidth (neighbors) |
|---|---|
| CONSTANT | 433 |
| ln_income | 18 |
| pct_black | 253 |
| pct_hispanic | 122 |
| pct_pre1950 | 157 |
| pct_renter | 766 |
| pct_multifam5 | 157 |

|   |   |   |
|---|---|---|
| ![mgwr_ln_income](figures/mgwr_ln_income.png) | ![mgwr_pct_black](figures/mgwr_pct_black.png) | ![mgwr_pct_hispanic](figures/mgwr_pct_hispanic.png) |

|   |   |   |
|---|---|---|
| ![mgwr_pct_multifam5](figures/mgwr_pct_multifam5.png) | ![mgwr_pct_pre1950](figures/mgwr_pct_pre1950.png) | ![mgwr_pct_renter](figures/mgwr_pct_renter.png) |

