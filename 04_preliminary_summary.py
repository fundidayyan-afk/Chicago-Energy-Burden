"""Step 4: the numbers for the proposal's 'Preliminary data work' paragraph.

Prints a ready-to-edit paragraph and saves it to output/tables/preliminary_summary.md.
Run after 02_build.py (and 03_explore.py if you want Moran's I included).
"""
import json

import geopandas as gpd

from ceb import config
from ceb.lead import weighted_median

if __name__ == "__main__":
    gdf = gpd.read_file(config.PROCESSED / "chicago_tracts.gpkg")
    s = gdf[gdf["in_main_sample"].astype(bool)]

    n_all, n = len(gdf), len(s)
    hh = s["households"].sum()
    city = 100 * s["energy_total"].sum() / s["income_total"].sum()
    li = s.dropna(subset=["li_burden_pct"])
    city_li = 100 * li["li_energy_total"].sum() / li["li_income_total"].sum()
    med_tract = weighted_median(s["burden_pct"], s["households"])
    q = s["burden_pct"].quantile([0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
    hi_share = (s["share_high"] * s["households"]).sum() / hh
    sev_share = (s["share_severe"] * s["households"]).sum() / hh
    li_med = weighted_median(li["li_burden_pct"], li["li_households"])

    moran = None
    mpath = config.TABLES / "moran.json"
    if mpath.exists():
        moran = json.loads(mpath.read_text())

    a24 = config.ACEEE_2024_CHICAGO
    text = (
        f"The LEAD 2022 data cover {n_all} census tracts that lie mostly within Chicago; after removing "
        f"tracts with too few households or missing covariates, {n} tracts and about {hh:,.0f} households remain. "
        f"Across all of them, households spend {city:.1f}% of income on energy. Tract burden ranges from "
        f"{q[0.0]:.1f}% to {q[1.0]:.1f}% (10th to 90th percentile: {q[0.1]:.1f}% to {q[0.9]:.1f}%), and the "
        f"household-weighted median tract burden is {med_tract:.1f}%. For households below 80% of area median "
        f"income, the citywide burden is {city_li:.1f}% and the median tract burden is {li_med:.1f}%, compared with ACEEE's 2024 estimate of "
        f"{a24['low_income_median']}% for low-income Chicago households ({a24['all_households_median']}% for all "
        f"households). About {100*hi_share:.0f}% of households live in income groups whose average burden is above "
        f"6%, and {100*sev_share:.0f}% above 10%."
    )
    if moran:
        text += (f" Burden is strongly clustered in space (global Moran's I = {moran['queen']['I']:.2f}, "
                 f"p < {max(moran['queen']['p_sim'], 1e-4):.4f}), with "
                 f"{moran['lisa_counts_fdr'].get('High-High', 0)} tracts in significant high-burden clusters "
                 f"after a false discovery rate correction.")
    note = ("\n\nCheck before using: ACEEE reports medians of household burdens, while the citywide figure "
            "above is total spending over total income. The two should be close in direction and size but "
            "are not the same statistic, so describe the comparison as a sanity check, not a match.")
    (config.TABLES / "preliminary_summary.md").write_text(text + note + "\n")
    print(text + note)
