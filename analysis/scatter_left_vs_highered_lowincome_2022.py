#!/usr/bin/env python3
"""
2022 first-round Left vote share vs higher-education share, restricted to the
bottom 30% of precincts by commune median disposable income. OLS trend only.

Higher education = highest diploma tertiary (Bac+2 and above) as a share of
people aged 15+ no longer in school (INSEE 2021). Minimal in-image text;
context in the README / caption.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

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

fig, ax = plt.subplots(figsize=(7, 5.2))
ax.scatter(x, y, s=4, alpha=0.12, color="#444444", linewidths=0, rasterized=True)
sl, ic = np.polyfit(x, y, 1, w=w)
gx = np.linspace(x.min(), x.max(), 200)
ax.plot(gx, ic + sl * gx, color="#c1121f", lw=2.4)
r = stats.pearsonr(x, y)[0]
ax.set_xlabel("Higher education (%)", fontsize=10)
ax.set_ylabel("Left vote share (%)", fontsize=10)
ax.set_ylim(0, min(100, y.max() + 5))
ax.grid(alpha=0.25, lw=0.5)
ax.text(0.97, 0.05, f"r = {r:+.2f}\nslope = {sl:+.2f}", transform=ax.transAxes,
        fontsize=9, ha="right", va="bottom", color="#c1121f")
fig.tight_layout()
out = os.path.join(OUTDIR, "left_vs_higher_ed_bottom30_income_2022.png")
fig.savefig(out, dpi=140)
print("saved", out, f"| cutoff €{cut:,.0f} n={len(low):,} r={r:+.3f} slope={sl:+.3f}")
