# Measurement error and heteroskedasticity

Margin-of-error simulation: 200 draws of every ACS input, spatial Durbin model refit each time, combined with Rubin's rules.

## Energy burden (%)

- Effects significant in the main model that stay significant after accounting for ACS measurement error: 7 of 9 (lost: % housing built before 1950 direct, % housing built before 1950 indirect).
- Largest share of an effect's variance due to measurement error: 65% (ln(median household income), direct).
- Direct effects with the same sign and significance under all five estimators (ML Durbin, S2SLS Durbin, GMM Durbin, SLX with spatial HAC, GMM spatial error): 3 of 6.
- Total effects with the same sign and significance in the ML Durbin model and the SLX model with spatial HAC standard errors: 6 of 6.
- Spatial lag parameter rho: GMM spatial Durbin, heteroskedasticity-robust 0.90 (SE 0.12); ML spatial Durbin (main) 0.62 (SE 0.04); S2SLS spatial Durbin, White SEs 0.96 (SE 0.12). The instrumental-variable estimators identify rho only weakly once neighbors' covariates are in the model, so their total effects (which divide by 1 - rho) are not used.

## ln(average energy cost)

- Effects significant in the main model that stay significant after accounting for ACS measurement error: 10 of 14 (lost: % Black direct, % Hispanic direct, % Hispanic total, % housing built before 1950 indirect).
- Largest share of an effect's variance due to measurement error: 58% (ln(median household income), direct).
- Direct effects with the same sign and significance under all five estimators (ML Durbin, S2SLS Durbin, GMM Durbin, SLX with spatial HAC, GMM spatial error): 3 of 6.
- Total effects with the same sign and significance in the ML Durbin model and the SLX model with spatial HAC standard errors: 6 of 6.
- Spatial lag parameter rho: GMM spatial Durbin, heteroskedasticity-robust 0.90 (SE 0.54); ML spatial Durbin (main) 0.56 (SE 0.04); S2SLS spatial Durbin, White SEs 0.90 (SE 0.14). The instrumental-variable estimators identify rho only weakly once neighbors' covariates are in the model, so their total effects (which divide by 1 - rho) are not used.

