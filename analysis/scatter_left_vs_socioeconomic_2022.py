#!/usr/bin/env python3
"""
Precinct-level scatter plots: 2022 first-round Left vote share vs socioeconomic
characteristics, with OLS + LOWESS trend lines.

Unit of observation: bureau de vote (polling precinct), metropolitan France,
2022 presidential election, round 1 (n ~ 67k).

  Y = total Left vote share  (Mélenchon + Jadot + Roussel + Hidalgo + Poutou +
      Arthaud) / exprimés * 100  -- reproduces the validated national 31.9%.
  X = commune-level 2021 census/Filosofi attribute attached to each precinct.

NOTE on granularity: the vote share is genuinely at the precinct level; the
socioeconomic X attributes are commune-level (INSEE 2021) attached to every
precinct of that commune. This is the lighter alternative to the repository's
full Tier B dasymetric interpolation (which needs the 676 MB BV contour layer +
Filosofi 200 m grid). Big cities split into arrondissement-communes (Paris,
Lyon, Marseille) so an urban gradient is still visible. These are ecological
(aggregate) relationships, not individual vote behaviour.

Input : bv_2022_analysis.parquet  (built by the companion data-prep step)
Output: outputs/figures_2022_precinct/*.png
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from statsmodels.nonparametric.smoothers_lowess import lowess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.environ.get("BV_DATA", os.path.join(ROOT, "data", "processed", "bv_2022_analysis.parquet"))
OUTDIR = os.path.join(ROOT, "outputs", "figures_2022_precinct")
os.makedirs(OUTDIR, exist_ok=True)

df = pd.read_parquet(DATA)

# (column, label, log_x)
VARS = [
    ("pop_density",       "Population density (inhab/km², log scale)", True),
    ("median_income",     "Median disposable income (€/yr, per cons. unit)", False),
    ("csp_cadres_pct",    "Managers & higher professions — cadres (% of employed)", False),
    ("csp_ouvriers_pct",  "Manual workers — ouvriers (% of employed)", False),
    ("csp_employes_pct",  "Clerical & service workers — employés (% of employed)", False),
    ("higher_ed_pct",     "Higher-education graduates (% of non-schooled 15+)", False),
    ("no_diploma_pct",    "No / low diploma (% of non-schooled 15+)", False),
]

YCOL = "left_share"
YLAB = "Left first-round vote share (%)"


def panel(ax, x, y, w, xlabel, logx):
    m = np.isfinite(x) & np.isfinite(y) & np.isfinite(w)
    x, y, w = x[m], y[m], w[m]
    xp = np.log10(x) if logx else x
    # scatter (small, translucent — 67k points)
    ax.scatter(x, y, s=3, alpha=0.10, color="#444444", linewidths=0, rasterized=True)
    if logx:
        ax.set_xscale("log")
    # OLS (weighted by exprimés) on the plotted x-metric
    sl, ic = np.polyfit(xp, y, 1, w=w)
    gx = np.linspace(xp.min(), xp.max(), 200)
    gxr = 10 ** gx if logx else gx
    ax.plot(gxr, ic + sl * gx, color="#c1121f", lw=2.2, label="OLS (weighted)")
    # LOWESS on a sample for speed
    n = len(xp)
    idx = np.random.default_rng(0).choice(n, size=min(n, 8000), replace=False)
    lo = lowess(y[idx], xp[idx], frac=0.4, return_sorted=True)
    lx = 10 ** lo[:, 0] if logx else lo[:, 0]
    ax.plot(lx, lo[:, 1], color="#1d3557", lw=2.2, ls="--", label="LOWESS")
    # stats (Pearson r on x-metric, weighted slope reported per unit)
    r = stats.pearsonr(xp, y)[0]
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(YLAB, fontsize=9)
    ax.set_ylim(0, min(100, y.max() + 5))
    ax.grid(alpha=0.25, lw=0.5)
    ax.set_title(f"r = {r:+.2f}   (n = {len(x):,})", fontsize=10, loc="left")
    ax.legend(fontsize=7, loc="upper right", framealpha=0.85)


# --- individual figures ---
saved = []
for col, lab, logx in VARS:
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    panel(ax, df[col].to_numpy(float), df[YCOL].to_numpy(float),
          df["exprimes"].to_numpy(float), lab, logx)
    fig.suptitle("French Left vote vs " + col, fontsize=12, fontweight="bold")
    fig.text(0.5, 0.005,
             "2022 presidential, round 1 — bureaux de vote (metropolitan France). "
             "Y: precinct-level; X: commune-level INSEE 2021.",
             ha="center", fontsize=7, color="#555555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    out = os.path.join(OUTDIR, f"left_vs_{col}.png")
    fig.savefig(out, dpi=130)
    plt.close(fig)
    saved.append(out)
    print("saved", out)

# --- combined grid ---
ncol = 2
nrow = int(np.ceil(len(VARS) / ncol))
fig, axes = plt.subplots(nrow, ncol, figsize=(13, 4.4 * nrow))
for ax, (col, lab, logx) in zip(axes.flat, VARS):
    panel(ax, df[col].to_numpy(float), df[YCOL].to_numpy(float),
          df["exprimes"].to_numpy(float), lab, logx)
for ax in axes.flat[len(VARS):]:
    ax.axis("off")
fig.suptitle("French Left first-round vote share (2022) vs socioeconomic characteristics — precinct level",
             fontsize=14, fontweight="bold")
fig.tight_layout(rect=(0, 0, 1, 0.985))
grid = os.path.join(OUTDIR, "left_vs_socioeconomic_grid_2022.png")
fig.savefig(grid, dpi=120)
plt.close(fig)
print("saved", grid)
print("DONE", len(saved) + 1, "figures")
