#!/usr/bin/env python3
"""
2022 first-round Left vote share vs higher-education share, restricted to the
BOTTOM 30% of precincts by commune median disposable income.

Higher education (higher_ed_pct), INSEE 2021 diplomes-formation file:
    100 * (P21_NSCOL15P_SUP2 + P21_NSCOL15P_SUP34 + P21_NSCOL15P_SUP5)
          / P21_NSCOL15P
  base   = people aged 15+ no longer in school (non scolarises 15+)
  numer. = highest diploma is tertiary / Bac+2 and above
           SUP2  = Bac+2 (BTS, DUT, ...)
           SUP34 = Bac+3 / Bac+4 (licence, maitrise)
           SUP5  = Bac+5 or higher (master, grande ecole, doctorat)

Bottom 30% = precincts whose commune median income is <= the 30th percentile of
median income across all precincts.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from statsmodels.nonparametric.smoothers_lowess import lowess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
df = pd.read_parquet(os.path.join(ROOT, "data", "processed", "bv_2022_analysis.parquet"))
OUTDIR = os.path.join(ROOT, "outputs", "figures_2022_precinct")
os.makedirs(OUTDIR, exist_ok=True)

d = df.dropna(subset=["median_income", "higher_ed_pct", "left_share"]).copy()
cut = d.median_income.quantile(0.30)
low = d[d.median_income <= cut].copy()

x = low.higher_ed_pct.to_numpy(float)
y = low.left_share.to_numpy(float)
w = low.exprimes.to_numpy(float)

fig, ax = plt.subplots(figsize=(8, 6))
ax.scatter(x, y, s=4, alpha=0.12, color="#444444", linewidths=0, rasterized=True)

# OLS, vote-weighted
sl, ic = np.polyfit(x, y, 1, w=w)
gx = np.linspace(x.min(), x.max(), 200)
ax.plot(gx, ic + sl * gx, color="#c1121f", lw=2.4,
        label=f"OLS (weighted): slope {sl:+.2f} pp / +1pp higher-ed")

# LOWESS
rng = np.random.default_rng(0)
idx = rng.choice(len(x), size=min(len(x), 8000), replace=False)
lo = lowess(y[idx], x[idx], frac=0.4, return_sorted=True)
ax.plot(lo[:, 0], lo[:, 1], color="#1d3557", lw=2.4, ls="--", label="LOWESS")

r = stats.pearsonr(x, y)[0]
wm = np.average(y, weights=w)
ax.set_xlabel("Higher-education graduates — Bac+2 and above\n(% of population aged 15+ no longer in school)", fontsize=10)
ax.set_ylabel("Left first-round vote share (%)", fontsize=10)
ax.set_ylim(0, min(100, y.max() + 5))
ax.grid(alpha=0.25, lw=0.5)
ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
ax.set_title(
    f"Bottom 30% of precincts by income (commune median ≤ €{cut:,.0f})\n"
    f"n = {len(low):,} precincts   |   r = {r:+.2f}   |   weighted Left share {wm:.1f}%",
    fontsize=11, loc="left")
fig.suptitle("2022 Left first-round vote vs higher education — lowest-income precincts",
             fontsize=13, fontweight="bold")
fig.text(0.5, 0.005,
         "2022 presidential round 1, bureaux de vote (metropolitan France). "
         "Y precinct-level; higher-ed & income commune-level INSEE 2021.",
         ha="center", fontsize=7.5, color="#555555")
fig.tight_layout(rect=(0, 0.02, 1, 0.96))
out = os.path.join(OUTDIR, "left_vs_higher_ed_bottom30_income_2022.png")
fig.savefig(out, dpi=140)
print("saved", out)
print(f"cutoff EUR {cut:,.0f}; n={len(low):,}; r={r:+.3f}; slope={sl:+.3f}; weighted Left {wm:.2f}%")
