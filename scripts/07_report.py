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


def coef_table(coefs, outcome):
    sub = coefs[coefs["model"].str.endswith(f": {outcome}")].copy()
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
        if coefs_path.exists():
            coefs = pd.read_csv(coefs_path)
            for outcome, label in [("burden_pct", "Energy burden (%)"),
                                   ("ln_avg_energy_cost", "ln(average energy cost)")]:
                tbl = coef_table(coefs, outcome)
                if tbl:
                    parts += [f"**{label}**: coefficient (standard error); * p<0.05, ** p<0.01, *** p<0.001", "",
                              tbl, ""]
        comp = t / "model_comparison.csv"
        if comp.exists():
            parts += ["**Model comparison**", "", pd.read_csv(comp).round(3).to_markdown(index=False), ""]
        for f in sorted(t.glob("lag_impacts_*.csv")):
            parts += [f"**Spatial lag effects ({f.stem.replace('lag_impacts_', '')})**", "",
                      pd.read_csv(f).round(4).to_markdown(index=False), ""]

    sec = read(t / "mgwr_summary.json")
    if sec:
        s = json.loads(sec)
        parts += ["## 5. Does it differ across the city? (RQ4)", "",
                  f"MGWR adjusted R² = {s['adj_r2']:.3f}; AICc = {s['aicc']:.1f}; "
                  f"max local condition number = {s['max_local_condition_number']:.1f}", "",
                  "| Variable | Bandwidth (neighbors) |", "|---|---|",
                  *[f"| {k} | {v:.0f} |" for k, v in s["bandwidths"].items()], ""]
        figs = sorted(config.FIGURES.glob("mgwr_*.png"))
        for i in range(0, len(figs), 3):
            row = figs[i:i + 3]
            parts += ["| " + " | ".join(" " for _ in row) + " |", "|" + "---|" * len(row),
                      "| " + " | ".join(f"![{f.stem}](figures/{f.name})" for f in row) + " |", ""]

    OUT.write_text("\n".join(parts) + "\n")
    print(f"Wrote {OUT}")
