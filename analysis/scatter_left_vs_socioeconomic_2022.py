#!/usr/bin/env python3
"""
Precinct-level scatter plots: 2022 first-round Left vote share vs socioeconomic
characteristics, with an OLS trend line.

Unit: bureau de vote (precinct), metropolitan France, 2022 presidential round 1.
  Y = total Left vote share (Melenchon+Jadot+Roussel+Hidalgo+Poutou+Arthaud).
  X = commune-level 2021 census/Filosofi attribute attached to each precinct.

Minimal in-image text (no titles/footnotes) -- context lives in the README and
file captions. See outputs/figures_2022_precinct/README.md for the granularity
caveat (X is commune-level; ecological relationships).

Input : data/processed/bv_2022_analysis.parquet
Output: outputs/figures_2022_precinct/*.png
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.environ.get("BV_DATA", os.path.join(ROOT, "data", "processed", "bv_2022_analysis.parquet"))
OUTDIR = os.path.join(ROOT, "outputs", "figures_2022_precinct")
os.makedirs(OUTDIR, exist_ok=True)

df = pd.read_parquet(DATA)

# (column, short label, log_x)
VARS = [
    ("pop_density",      "Population density (log)", True),
    ("median_income",    "Median income (€)", False),
    ("csp_cadres_pct",   "% cadres", False),
    ("csp_ouvriers_pct", "% ouvriers", False),
    ("csp_employes_pct", "% employés", False),
    ("higher_ed_pct",    "Higher education (%)", False),
    ("no_diploma_pct",   "No/low diploma (%)", False),
]
YCOL, YLAB = "left_share", "Left vote share (%)"


def panel(ax, x, y, w, xlabel, logx):
    m = np.isfinite(x) & np.isfinite(y) & np.isfinite(w)
    x, y, w = x[m], y[m], w[m]
    xp = np.log10(x) if logx else x
    ax.scatter(x, y, s=3, alpha=0.10, color="#444444", linewidths=0, rasterized=True)
    if logx:
        ax.set_xscale("log")
    sl, ic = np.polyfit(xp, y, 1, w=w)
    gx = np.linspace(xp.min(), xp.max(), 200)
    ax.plot(10 ** gx if logx else gx, ic + sl * gx, color="#c1121f", lw=2.2)
    r = stats.pearsonr(xp, y)[0]
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(YLAB, fontsize=9)
    ax.set_ylim(0, min(100, y.max() + 5))
    ax.grid(alpha=0.25, lw=0.5)
    ax.text(0.97, 0.04, f"r = {r:+.2f}", transform=ax.transAxes,
            fontsize=9, ha="right", va="bottom", color="#c1121f")


# --- individual figures ---
for col, lab, logx in VARS:
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    panel(ax, df[col].to_numpy(float), df[YCOL].to_numpy(float),
          df["exprimes"].to_numpy(float), lab, logx)
    fig.tight_layout()
    out = os.path.join(OUTDIR, f"left_vs_{col}.png")
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print("saved", out)

# --- combined grid ---
ncol = 2
nrow = int(np.ceil(len(VARS) / ncol))
fig, axes = plt.subplots(nrow, ncol, figsize=(11, 3.6 * nrow))
for ax, (col, lab, logx) in zip(axes.flat, VARS):
    panel(ax, df[col].to_numpy(float), df[YCOL].to_numpy(float),
          df["exprimes"].to_numpy(float), lab, logx)
for ax in axes.flat[len(VARS):]:
    ax.axis("off")
fig.tight_layout()
grid = os.path.join(OUTDIR, "left_vs_socioeconomic_grid_2022.png")
fig.savefig(grid, dpi=120)
plt.close(fig)
print("saved", grid)
