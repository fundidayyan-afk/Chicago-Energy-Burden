"""Step 7: gather every output into output/RESULTS.md, which GitHub displays as a page.

Works with partial results: sections whose files do not exist yet are skipped.
"""
import datetime as dt
import json

import pandas as pd

from ceb import config

OUT = config.OUTPUT / "RESULTS.md"


def read(path):
    return path.read_text() if path.exists() else None


def img(name, alt):
    p = config.FIGURES / name
    return f"![{alt}](figures/{name})" if p.exists() else None


def stars(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""


def impacts_table(path):
    """Main-model effects: direct / indirect / total, estimate (SE or 95% CI)."""
    d = pd.read_csv(path)
    d["cell"] = d.apply(lambda r: f"{r.estimate:.4f}{stars(r.p)} [{r.ci_low:.4f}, {r.ci_high:.4f}]", axis=1)
    wide = d.pivot_table(index="label", columns="effect", values="cell", aggfunc="first", sort=False)
    return wide[[c for c in ("direct", "indirect", "total") if c in wide.columns]].to_markdown()


def coef_table(coefs, outcome):
    sub = coefs[coefs["spec"] == outcome].copy() if "spec" in coefs else \
        coefs[coefs["model"].str.endswith(f": {outcome}")].copy()
    if sub.empty:
        return None

    def cell(r):
        stars = "***" if r.p < 0.001 else "**" if r.p < 0.01 else "*" if r.p < 0.05 else ""
        return f"{r.coef:.3f}{stars} ({r.se:.3f})"

    sub["cell"] = sub.apply(cell, axis=1)
    wide = sub.pivot_table(index="label", columns="model", values="cell", aggfunc="first", sort=False)
    wide.columns = [c.split(":")[0] for c in wide.columns]
    return wide.fillna("").to_markdown()


if __name__ == "__main__":
    t = config.TABLES
    parts = ["# Results: Household Energy Burden Across Chicago", "",
             f"_Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by the pipeline. "
             "Do not edit by hand; rerun the workflow instead._", ""]

    status = read(config.OUTPUT / "run_log.txt")
    if status and "FAILED at" in status:
        failed = [l for l in status.splitlines() if l.startswith("FAILED at")][-1]
        parts += [f"> **The last run stopped early ({failed}).** See [run_log.txt](run_log.txt). "
                  "Sections below show whatever finished.", ""]

    sec = read(t / "exclusions.md")
    if sec:
        parts += ["## 1. Sample", "", sec.replace("# Sample construction log", "").strip(), ""]

    sec = read(t / "preliminary_summary.md")
    if sec:
        parts += ["## 2. Summary", "", sec.strip(), ""]

    maps = [m for m in (img("map_burden.png", "Energy burden map"), img("map_lisa.png", "LISA cluster map")) if m]
    moran = read(t / "moran.json")
    if maps or moran:
        parts += ["## 3. Where is burden concentrated? (RQ1)", ""]
        if moran:
            m = json.loads(moran)
            rows = [f"| {k} | {m[k]['I']:.3f} | {m[k]['p_sim']:.4f} |" for k in ("queen", "knn") if k in m]
            parts += ["| Weights | Global Moran's I | p (permutation) |", "|---|---|---|", *rows, "",
                      f"LISA clusters at 5% FDR: {m.get('lisa_counts_fdr')}", ""]
        if len(maps) == 2:
            parts += ["| Burden | Clusters |", "|---|---|", f"| {maps[0]} | {maps[1]} |", ""]
        else:
            parts += maps + [""]

    sec = read(t / "model_selection.md")
    coefs_path = t / "coefficients.csv"
    if sec or coefs_path.exists():
        parts += ["## 4. What explains it? (RQ2 and RQ3)", ""]
        vif = t / "vif.csv"
        if vif.exists():
            parts += ["**Variance inflation factors**", "",
                      pd.read_csv(vif, index_col=0).round(2).to_markdown(), ""]
        if sec:
            parts += [sec.replace("# Model selection", "").replace("## ", "### ").strip(), ""]
        lr = t / "lr_tests.csv"
        if lr.exists():
            d = pd.read_csv(lr)
            parts += ["**Choosing the main model** (likelihood ratio tests nesting the spatial error and lag "
                      "models inside the spatial Durbin model)", "",
                      "| Outcome | LM tests chose | Common factor LR (p) | Durbin vs lag LR (p) | AIC error / lag / Durbin | Main model |",
                      "|---|---|---|---|---|---|",
                      *[f"| {r.spec} | {r.lm_choice} | {r.lr_common_factor:.1f} ({r.p_common_factor:.4f}) | "
                        f"{r.lr_durbin_vs_lag:.1f} ({r.p_durbin_vs_lag:.4f}) | {r.aic_error:.1f} / {r.aic_lag:.1f} / "
                        f"{r.aic_durbin:.1f} | **{r.choice}** |" for r in d.itertuples()], ""]
        mm = t / "main_models.json"
        if mm.exists():
            main = json.loads(mm.read_text())
            parts += ["### Effects from the main models", "",
                      "Estimate with 95% interval; * p<0.05, ** p<0.01, *** p<0.001. For a spatial Durbin or lag "
                      "model, direct = effect of a tract's own characteristics, indirect = spillover from "
                      "neighbors, total = both. For a spatial error model, the coefficients are the effects.", ""]
            for spec, info in main.items():
                f = t / f"impacts_{spec}.csv"
                if f.exists():
                    parts += [f"**{info['label']}** ({info['model']} model)", "", impacts_table(f), ""]
        for name, alt in [("effects_burden_costs.png", "Effects on burden and bills"),
                          ("effects_fuels.png", "Effects on electricity and gas burden")]:
            im = img(name, alt)
            if im:
                parts += [im, ""]
        if coefs_path.exists():
            coefs = pd.read_csv(coefs_path)
            parts += ["### All coefficients", "", "Coefficient (standard error); * p<0.05, ** p<0.01, *** p<0.001.", ""]
            specs = coefs["spec"].unique() if "spec" in coefs else ["burden_pct", "ln_avg_energy_cost"]
            for spec in specs:
                tbl = coef_table(coefs, spec)
                if tbl:
                    parts += [f"**{spec}**", "", tbl, ""]
        comp = t / "model_comparison.csv"
        if comp.exists():
            parts += ["**Model comparison**", "", pd.read_csv(comp).round(3).to_markdown(index=False), ""]

    mc = t / "model_comparison_burden.csv"
    sec = read(t / "mgwr_summary.json")
    if sec:
        s = json.loads(sec)
        parts += ["## 5. Does it differ across the city? (RQ4)", "",
                  f"MGWR adjusted R² = {s['adj_r2']:.3f}; AICc = {s['aicc']:.1f}; "
                  f"max local condition number = {s['max_local_condition_number']:.1f}", "",
                  "| Variable | Bandwidth (neighbors) |", "|---|---|",
                  *[f"| {k} | {v:.0f} |" for k, v in s["bandwidths"].items()], ""]
        if mc.exists():
            parts += ["**Model comparison, energy burden** (all on the original scale; lower AIC is better)", "",
                      pd.read_csv(mc).round(3).fillna("").to_markdown(index=False), ""]
        figs = sorted(config.FIGURES.glob("mgwr_*.png"))
        for i in range(0, len(figs), 3):
            row = figs[i:i + 3]
            parts += ["| " + " | ".join(" " for _ in row) + " |", "|" + "---|" * len(row),
                      "| " + " | ".join(f"![{f.stem}](figures/{f.name})" for f in row) + " |", ""]

    rob = sorted(t.glob("robustness_*.csv"))
    rob = [f for f in rob if f.stem != "robustness_long"]
    if rob:
        parts += ["## 6. Robustness checks", "",
                  "Each column changes one thing relative to the main spatial error model. "
                  "Coefficient (standard error); * p<0.05, ** p<0.01, *** p<0.001.", ""]
        notes = read(t / "robustness_notes.md")
        if notes:
            parts += [notes.replace("# Robustness checks", "").strip(), ""]
        for f in rob:
            name = {"robustness_burden_pct": "Energy burden (%)",
                    "robustness_burden_pct_total": "Energy burden (%), total effects",
                    "robustness_ln_avg_energy_cost": "ln(average energy cost)",
                    "robustness_ln_avg_energy_cost_total": "ln(average energy cost), total effects"}.get(f.stem, f.stem)
            parts += [f"**{name}**", "", pd.read_csv(f, index_col=0).fillna("").to_markdown(), ""]
        thr = t / "threshold_models.csv"
        if thr.exists():
            d = pd.read_csv(thr)
            d = d[d["model"].str.startswith("Fractional") & (d["term"] != "CONSTANT")]
            d["cell"] = d.apply(lambda r: f"{r.ame:.4f}{'***' if r.p < .001 else '**' if r.p < .01 else '*' if r.p < .05 else ''} ({r.ame_se:.4f})", axis=1)
            w = d.pivot(index="label", columns="model", values="cell")
            w.columns = [c.replace("Fractional logit: share_high", "Share above 6%")
                          .replace("Fractional logit: share_severe", "Share above 10%") for c in w.columns]
            parts += ["**Share of households above the 6% and 10% lines** (fractional logit, average "
                      "marginal effects; shares are lower bounds, see method notes)", "", w.to_markdown(), ""]
        val = read(t / "validation.json")
        if val:
            v = json.loads(val)
            if "error" in v:
                parts += [f"**Independent ACS burden check:** skipped ({v['error']})", ""]
            else:
                parts += ["**Independent ACS burden check** (LEAD vs. ACS utility-cost tables)", "",
                          "| Measure | Pearson r | Spearman rho | Top-20% overlap | n |", "|---|---|---|---|---|",
                          *[f"| {k.replace('_', ' ')} | {v[k]['pearson']:.2f} | {v[k]['spearman']:.2f} | "
                            f"{v[k]['top_quintile_overlap']:.0%} | {v[k]['n']} |" for k in ("burden", "annual_cost")],
                          "", f"_{v['note']}_", ""]
                im = img("validation_scatter.png", "LEAD vs ACS")
                if im:
                    parts += [im, ""]

    pol = read(t / "policy_summary.md")
    if pol:
        parts += ["## 7. Policy analysis", "", pol.replace("# Policy analysis", "").strip(), ""]
        tg = t / "policy_targeting.csv"
        if tg.exists():
            d = pd.read_csv(tg)
            parts += ["**Targeting rules**", "",
                      "| Budget | Rule | Tracts | Households | Above 10% | Share of city above 10% | Above 6% | Share of city above 6% | Overlap with clusters |",
                      "|---|---|---|---|---|---|---|---|---|",
                      *[f"| {r.budget} | {r.rule} | {r.tracts} | {r.households:,.0f} | {r.hh_above_10:,.0f} | "
                        f"{r.share_of_city_above_10:.1%} | {r.hh_above_6:,.0f} | {r.share_of_city_above_6:.1%} | "
                        f"{r.overlap_with_clusters} |" for r in d.itertuples()], ""]
        im = img("map_priority.png", "Priority tracts")
        if im:
            parts += [im, ""]
        pa = t / "priority_by_community_area.csv"
        if pa.exists():
            parts += ["**Priority tracts by community area (top 15)**", "",
                      pd.read_csv(pa).head(15).to_markdown(index=False), ""]
        sc = t / "policy_scenarios.csv"
        if sc.exists():
            d = pd.read_csv(sc)
            parts += ["**Cost-cut scenarios in the priority tracts**", "",
                      "| Who | Cut | Households served | Burden before / after | Low-income burden before / after | Above 6% before / after | Above 10% before / after | Savings per served household |",
                      "|---|---|---|---|---|---|---|---|",
                      *[f"| {r.who} | {r.cost_cut:.0%} | {r.households_served:,.0f} | {r.burden_before:.2f}% / "
                        f"{r.burden_after:.2f}% | {r.li_burden_before:.2f}% / {r.li_burden_after:.2f}% | "
                        f"{r.above_6_before:,.0f} / {r.above_6_after:,.0f} | {r.above_10_before:,.0f} / "
                        f"{r.above_10_after:,.0f} | ${r.annual_savings_per_served_hh:,.0f} |" for r in d.itertuples()], ""]

    bm = read(t / "benchmarking_summary.json")
    if bm:
        b = json.loads(bm)
        parts += ["## 8. Context: large multifamily buildings (Chicago Energy Benchmarking)", ""]
        if "error" in b:
            parts += [f"_Skipped: {b['error']}_", ""]
        else:
            parts += [f"{b['multifamily_buildings']:,} benchmarked multifamily buildings ({b['data_year']}). "
                      f"Median site energy use intensity: {b['median_site_eui_high_burden_clusters']:.1f} kBtu/sq ft "
                      f"in high-burden cluster tracts ({b['buildings_in_high_burden_clusters']} buildings) vs. "
                      f"{b['median_site_eui_elsewhere']:.1f} elsewhere (Mann-Whitney p = {b['mann_whitney_p']:.3f}).", ""]
            for f, title in [("benchmarking_by_cluster.csv", "By burden cluster"),
                             ("benchmarking_by_era.csv", "By year built")]:
                if (t / f).exists():
                    parts += [f"**{title}**", "", pd.read_csv(t / f).round(1).to_markdown(index=False), ""]
            parts += [f"_{b['note']}_", ""]
    unc = read(t / "uncertainty_summary.md")
    if unc:
        parts += ["## 9. Measurement error and heteroskedasticity", "",
                  unc.replace("# Measurement error and heteroskedasticity", "").replace("## ", "### ").strip(), ""]
        for outcome, name in [("burden_pct", "Energy burden (%)"), ("ln_avg_energy_cost", "ln(average energy cost)")]:
            f = t / f"moe_combined_{outcome}.csv"
            if f.exists():
                d = pd.read_csv(f)
                d = d[d["effect"] != "indirect"]
                parts += [f"**{name}: original vs. measurement-error-adjusted (Rubin) effects**", "",
                          "| Variable | Effect | Original | Adjusted (SE) | p | Range across draws | Share of variance from ACS error |",
                          "|---|---|---|---|---|---|---|",
                          *[f"| {r.label} | {r.effect} | {r.original_estimate:.4f}{stars(r.original_p)} | "
                            f"{r.moe_estimate:.4f} ({r.moe_se:.4f}) | {r.moe_p:.4f} | [{r.moe_draw_low:.4f}, "
                            f"{r.moe_draw_high:.4f}] | {r.moe_share_variance_from_measurement:.0%} |" for r in d.itertuples()], ""]
            f = t / f"robust_estimators_{outcome}.csv"
            if f.exists():
                d = pd.read_csv(f)
                d = d[d["effect"] == "total"]
                d["cell"] = d.apply(lambda r: f"{r.estimate:.4f}{stars(r.p)}", axis=1)
                parts += [f"**{name}: total effects by estimator**", "",
                          d.pivot(index="label", columns="estimator", values="cell").to_markdown(), ""]
    prof = t / "typology_profiles.csv"
    if prof.exists():
        d = pd.read_csv(prof)
        sil = pd.read_csv(t / "typology_silhouette.csv")
        parts += ["## 10. Neighborhood typology", "",
                  f"k-means on nine standardized tract characteristics; k = {len(d)} chosen by silhouette score "
                  f"({sil['silhouette'].max():.2f}; scores for k = 3 to 8: "
                  f"{', '.join(f'{v:.2f}' for v in sil['silhouette'])}).", "",
                  "| Type | Label | Tracts | Households | Burden (%) | Median income | Avg. energy cost | % Black | % Hispanic | % pre-1950 | % renter | In high-burden clusters |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|",
                  *[f"| {r.type} | {r.label} | {r.tracts} | {r.households:,.0f} | {r.burden_pct:.2f} | "
                    f"${r.median_income:,.0f} | ${r.avg_energy_cost:,.0f} | {r.pct_black:.0f} | {r.pct_hispanic:.0f} | "
                    f"{r.pct_pre1950:.0f} | {r.pct_renter:.0f} | {r.share_in_high_burden_clusters:.0%} |"
                    for r in d.itertuples()], ""]
        im = img("map_typology.png", "Neighborhood types")
        if im:
            parts += [im, ""]
    parts += ["## Notebooks", "", "Step-by-step notebooks with live outputs are in "
              "[`notebooks/`](../notebooks/).", ""]

    OUT.write_text("\n".join(parts) + "\n")
    print(f"Wrote {OUT}")
