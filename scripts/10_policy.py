"""Step 10: policy analysis on LEAD household groups.

  A. Targeting: high-burden clusters vs. lowest median income vs. highest
     poverty rate vs. highest measured burden (a best-case benchmark), at the
     same number of tracts and at the same number of households served.
  B. Scenario: 10%, 20%, and 30% energy cost cuts in the priority tracts
     (the high-burden clusters), for all households or only low-income ones.

Outputs in output/tables/: policy_targeting.csv, policy_scenarios.csv,
priority_tracts.csv, policy_summary.md.
"""
import geopandas as gpd
import pandas as pd

from ceb import config, lead, policy

if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    tr = pd.DataFrame(gdf[gdf["in_main_sample"].astype(bool)].drop(columns="geometry"))
    lisa = pd.read_csv(config.TABLES / "lisa_clusters.csv", dtype={"GEOID": str})
    tr = tr.merge(lisa[["GEOID", "cluster"]], on="GEOID", how="left")

    raw = pd.read_csv(lead.find_lead_csv(kind="AMI"), low_memory=False)
    fip = raw["FIP"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(11)
    coh = lead.cohorts(raw[fip.isin(set(tr["GEOID"]))])
    print(f"LEAD household groups in the sample: {len(coh):,} ({coh['units'].sum():,.0f} households)")

    clusters = tr.loc[tr["cluster"] == "High-High", "GEOID"].tolist()
    rules = {
        "Lowest median income": ("med_hh_income", True),
        "Highest poverty rate": ("pct_below_poverty", False),
        "Highest measured burden (benchmark)": ("burden_pct", False),
    }
    tgt = policy.targeting(tr, coh, clusters, rules)
    city = tgt.attrs["city"]
    tgt.to_csv(config.TABLES / "policy_targeting.csv", index=False)
    print(f"\nCity: {city['households']:,.0f} households; {city['hh_above_6']:,.0f} above 6%; "
          f"{city['hh_above_10']:,.0f} above 10%")
    print(tgt.round(3).to_string(index=False))

    sc = policy.scenarios(coh, clusters)
    sc.to_csv(config.TABLES / "policy_scenarios.csv", index=False)
    print("\n" + sc.round(2).to_string(index=False))

    pri = tr[tr["GEOID"].isin(clusters)][["GEOID", "NAMELSAD", "burden_pct", "li_burden_pct", "share_severe",
                                          "households", "med_hh_income"]].sort_values("burden_pct", ascending=False)
    pri.to_csv(config.TABLES / "priority_tracts.csv", index=False)

    same_tr = tgt[tgt["budget"] == "Same number of tracts"].set_index("rule")
    same_hh = tgt[tgt["budget"] == "Same number of households"].set_index("rule")
    best = same_hh["hh_above_10"].drop("Highest measured burden (benchmark)").idxmax()
    s20 = sc[(sc["cost_cut"] == 0.20) & (sc["who"] == "All households")].iloc[0]
    s20li = sc[(sc["cost_cut"] == 0.20) & (sc["who"].str.startswith("Low-income"))].iloc[0]
    lines = [
        "# Policy analysis", "",
        f"- Sample: {city['households']:,.0f} households; {city['hh_above_6']:,.0f} in groups above 6% and "
        f"{city['hh_above_10']:,.0f} above 10%.",
        f"- Priority tracts (high-burden clusters): {len(clusters)} tracts, "
        f"{same_tr.loc['High-burden clusters (LISA)', 'households']:,.0f} households.",
        f"- Serving the same number of households, the rule that reaches the most severely burdened households "
        f"(excluding the benchmark) is **{best}**: "
        f"{same_hh.loc[best, 'hh_above_10']:,.0f} ({same_hh.loc[best, 'share_of_city_above_10']:.1%} of the city's), "
        f"versus {same_hh.loc['High-burden clusters (LISA)', 'hh_above_10']:,.0f} for the clusters and "
        f"{same_hh.loc['Highest measured burden (benchmark)', 'hh_above_10']:,.0f} for the benchmark.",
        f"- A 20% cost cut for every household in the priority tracts lowers their burden from "
        f"{s20['burden_before']:.2f}% to {s20['burden_after']:.2f}% and moves {s20['dropped_below_6']:,.0f} "
        f"households below 6% ({s20['dropped_below_10']:,.0f} below 10%), saving about "
        f"${s20['annual_savings_per_served_hh']:,.0f} per household per year.",
        f"- The same cut limited to the {s20li['households_served']:,.0f} low-income households there moves "
        f"{s20li['dropped_below_6']:,.0f} below 6% and lowers their burden from {s20li['li_burden_before']:.2f}% "
        f"to {s20li['li_burden_after']:.2f}%.",
        "", "_Counts use LEAD household-group averages, so they approximate how many households cross each line._",
    ]
    (config.TABLES / "policy_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
