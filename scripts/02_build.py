"""Step 2: build the analysis-ready tract dataset and log every exclusion.

Output:
  data/processed/chicago_tracts.gpkg   one row per Chicago tract, all variables
  output/tables/exclusions.md          what was flagged or dropped, and why
"""
import pandas as pd

from ceb import acs, config, geo, lead

if __name__ == "__main__":
    tracts = geo.chicago_tracts(config.RAW / f"tiger_tracts_{config.TIGER_YEAR}",
                                config.RAW / f"tiger_places_{config.TIGER_YEAR}")
    print(f"Chicago tracts (>= {config.CITY_OVERLAP_MIN:.0%} of land in city): {len(tracts)}")

    lead_csv = lead.find_lead_csv(kind="AMI")
    print(f"LEAD file: {lead_csv.name}")
    lead_raw = pd.read_csv(lead_csv, low_memory=False)
    print(f"LEAD rows: {len(lead_raw):,}; columns: {list(lead_raw.columns)}")
    burden = lead.tract_burden(lead_raw)
    print(f"LEAD column mapping used: {burden.attrs.get('column_map')}")
    diag = burden.attrs["bracket_diagnostics"]
    diag.to_csv(config.TABLES / "lead_bracket_diagnostics.csv")
    print("LEAD by income bracket (all Illinois rows):\n" + diag.to_string())
    print("First 5 LEAD rows:\n" + lead_raw.head().to_string())

    cov = acs.build_covariates(acs.load_acs(config.RAW / f"acs5_{config.ACS_YEAR}_tracts.csv"))

    gdf = (tracts.merge(burden.rename(columns={"tract": "GEOID"}), on="GEOID", how="left")
                 .merge(cov, on="GEOID", how="left"))

    gdf["flag_no_lead"] = gdf["households"].isna()
    gdf["flag_few_households"] = gdf["households"].fillna(0) < config.MIN_HOUSEHOLDS
    gdf["flag_acs_unreliable"] = acs.flag_unreliable(gdf, config.ACS_CV_UNRELIABLE)
    gdf["flag_missing_covariate"] = gdf[["ln_income", "pct_black", "pct_hispanic", "pct_pre1950",
                                         "pct_renter", "pct_multifam5"]].isna().any(axis=1)
    gdf["in_main_sample"] = ~(gdf["flag_no_lead"] | gdf["flag_few_households"] | gdf["flag_missing_covariate"])

    out = config.PROCESSED / "chicago_tracts.gpkg"
    gdf.to_file(out, driver="GPKG")

    lines = ["# Sample construction log", "",
             f"- Tracts with >= {config.CITY_OVERLAP_MIN:.0%} of land area in Chicago: {len(gdf)}",
             f"- LEAD households dropped for zero/negative cohort income: "
             f"{burden.attrs.get('households_dropped_nonpositive_income', 'n/a')}"]
    for col, why in [("flag_no_lead", "no LEAD record"),
                     ("flag_few_households", f"fewer than {config.MIN_HOUSEHOLDS} households"),
                     ("flag_missing_covariate", "a model covariate is missing"),
                     ("flag_acs_unreliable", f"an ACS covariate has CV > {config.ACS_CV_UNRELIABLE} (kept; dropped in robustness)")]:
        ids = gdf.loc[gdf[col], "GEOID"].tolist()
        lines.append(f"- {why}: {len(ids)}" + (f"  \n  `{', '.join(ids[:40])}`" if 0 < len(ids) <= 40 else ""))
    lines.append(f"- **Main analysis sample: {int(gdf['in_main_sample'].sum())} tracts**")
    (config.TABLES / "exclusions.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"Saved {out}")
