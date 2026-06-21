#!/usr/bin/env python3
"""
Side-by-side: 2002 vs 2022 first-round Left vote share vs higher-education share,
restricted to the bottom 30% of precincts by median income. OLS trend only.

Each election paired with the nearest-available INSEE census/Filosofi vintage
(no Filosofi income before 2012): 2002 -> 2012 census, 2022 -> 2021 census.
Higher education = highest diploma tertiary (Bac+2 and above) as a share of
people aged 15+ no longer in school. Minimal in-image text; context in README.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
OUTDIR = os.path.join(ROOT, "outputs", "figures_2022_precinct")
os.makedirs(OUTDIR, exist_ok=True)

YEARS = {
    2002: ("bv_2002_analysis_c2012.parquet", 2012),
    2022: ("bv_2022_analysis.parquet", 2021),
}


def prep(fn):
    d = pd.read_parquet(os.path.join(PROC, fn)).dropna(
        subset=["median_income", "higher_ed_pct", "left_share"]).copy()
    cut = d.median_income.quantile(0.30)
    return d[d.median_income <= cut].copy(), cut


def panel(ax, low, year, vintage, xlim, ylim):
    x = low.higher_ed_pct.to_numpy(float)
    y = low.left_share.to_numpy(float)
    w = low.exprimes.to_numpy(float)
    ax.scatter(x, y, s=4, alpha=0.12, color="#444444", linewidths=0, rasterized=True)
    sl, ic = np.polyfit(x, y, 1, w=w)
    gx = np.linspace(x.min(), x.max(), 200)
    ax.plot(gx, ic + sl * gx, color="#c1121f", lw=2.4)
    r = stats.pearsonr(x, y)[0]
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.grid(alpha=0.25, lw=0.5)
    ax.set_xlabel(f"Higher education (%) — INSEE {vintage}", fontsize=9)
    ax.set_ylabel("Left vote share (%)", fontsize=9)
    ax.text(0.04, 0.96, str(year), transform=ax.transAxes, fontsize=12,
            ha="left", va="top", fontweight="bold")
    ax.text(0.97, 0.05, f"r = {r:+.2f}\nslope = {sl:+.2f}", transform=ax.transAxes,
            fontsize=9, ha="right", va="bottom", color="#c1121f")


sets = {y: (prep(v[0])[0], v[1]) for y, v in YEARS.items()}
allx = np.concatenate([low.higher_ed_pct.to_numpy(float) for low, _ in sets.values()])
xlim = (0, np.nanpercentile(allx, 99.5))
ylim = (0, 75)

fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), sharey=True)
for ax, y in zip(axes, [2002, 2022]):
    low, vintage = sets[y]
    panel(ax, low, y, vintage, xlim, ylim)
fig.tight_layout()
out = os.path.join(OUTDIR, "left_vs_higher_ed_bottom30_income_2002_vs_2022.png")
fig.savefig(out, dpi=140)
print("saved", out)
