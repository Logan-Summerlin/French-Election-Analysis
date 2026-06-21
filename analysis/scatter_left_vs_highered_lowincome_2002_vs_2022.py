#!/usr/bin/env python3
"""
Side-by-side: 2002 vs 2022 first-round Left vote share vs higher-education share,
restricted to the BOTTOM 30% of precincts by median income.

Each election is paired with the NEAREST-AVAILABLE INSEE census/Filosofi vintage
(Filosofi income does not exist before 2012):
    2002 election  ->  2012 census + Filosofi 2012   (first Filosofi millesime)
    2022 election  ->  2021 census + Filosofi 2021
Both the income filter and the higher-education axis use that election's vintage.

Higher education (higher_ed_pct) = highest diploma is tertiary, Bac+2 and above,
as a share of people aged 15+ no longer in school (non scolarises 15+):
    2012: 100 * (P12_NSCOL15P_BACP2 + P12_NSCOL15P_SUP) / P12_NSCOL15P
    2021: 100 * (P21_NSCOL15P_SUP2 + P21_NSCOL15P_SUP34 + P21_NSCOL15P_SUP5)
                / P21_NSCOL15P
(BACP2/SUP2 = Bac+2; SUP / SUP34+SUP5 = Bac+3 and above.)

Left coalition (data/lookups/left_classification.csv, is_left==1):
  2002: Jospin, Hue, Mamere, Taubira, Chevenement, Besancenot, Laguiller, Gluckstein
  2022: Melenchon, Jadot, Roussel, Hidalgo, Poutou, Arthaud

Bottom 30% = precincts whose commune median income <= the 30th percentile of
median income within that election's precinct set.
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
PROC = os.path.join(ROOT, "data", "processed")
OUTDIR = os.path.join(ROOT, "outputs", "figures_2022_precinct")
os.makedirs(OUTDIR, exist_ok=True)

# year -> (analysis parquet, census vintage label)
YEARS = {
    2002: ("bv_2002_analysis_c2012.parquet", 2012),
    2022: ("bv_2022_analysis.parquet", 2021),
}


def prep(fn):
    d = pd.read_parquet(os.path.join(PROC, fn)).dropna(
        subset=["median_income", "higher_ed_pct", "left_share"]).copy()
    cut = d.median_income.quantile(0.30)
    return d[d.median_income <= cut].copy(), cut


def panel(ax, low, year, vintage, cut, xlim, ylim):
    x = low.higher_ed_pct.to_numpy(float)
    y = low.left_share.to_numpy(float)
    w = low.exprimes.to_numpy(float)
    ax.scatter(x, y, s=4, alpha=0.12, color="#444444", linewidths=0, rasterized=True)
    sl, ic = np.polyfit(x, y, 1, w=w)
    gx = np.linspace(x.min(), x.max(), 200)
    ax.plot(gx, ic + sl * gx, color="#c1121f", lw=2.4, label=f"OLS: {sl:+.2f} pp / +1pp")
    idx = np.random.default_rng(0).choice(len(x), size=min(len(x), 8000), replace=False)
    lo = lowess(y[idx], x[idx], frac=0.4, return_sorted=True)
    ax.plot(lo[:, 0], lo[:, 1], color="#1d3557", lw=2.4, ls="--", label="LOWESS")
    r = stats.pearsonr(x, y)[0]
    wm = np.average(y, weights=w)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.grid(alpha=0.25, lw=0.5)
    ax.set_xlabel(f"Higher-education graduates — Bac+2 and above\n"
                  f"(% of 15+ no longer in school, INSEE {vintage})", fontsize=9)
    ax.set_ylabel("Left first-round vote share (%)", fontsize=9)
    ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
    ax.set_title(f"{year} election (census {vintage})   |   n = {len(low):,}   "
                 f"r = {r:+.2f}   weighted Left {wm:.1f}%",
                 fontsize=10.5, loc="left", fontweight="bold")
    return dict(year=year, vintage=vintage, n=len(low), r=r, slope=sl, wmean=wm, cut=cut)


sets = {y: (prep(v[0]) + (v[1],)) for y, v in YEARS.items()}  # year -> (low, cut, vintage)
allx = np.concatenate([s[0].higher_ed_pct.to_numpy(float) for s in sets.values()])
xlim = (0, np.nanpercentile(allx, 99.5))
ylim = (0, 75)

fig, axes = plt.subplots(1, 2, figsize=(14, 6.2), sharey=True)
rows = []
for ax, y in zip(axes, [2002, 2022]):
    low, cut, vintage = sets[y]
    rows.append(panel(ax, low, y, vintage, cut, xlim, ylim))

fig.suptitle("French Left first-round vote vs higher education — lowest-income precincts (bottom 30%)\n"
             "2002 vs 2022, bureaux de vote (metropolitan France); each election paired with nearest INSEE census",
             fontsize=13, fontweight="bold")
fig.text(0.5, 0.005,
         "Bottom 30% by commune median income (2002/2012 cutoff EUR {:.0f}; 2022/2021 cutoff EUR {:.0f}). "
         "Y precinct-level; income & higher-ed commune-level. Ecological relationships."
         .format(rows[0]["cut"], rows[1]["cut"]),
         ha="center", fontsize=7.5, color="#555555")
fig.tight_layout(rect=(0, 0.025, 1, 0.93))
out = os.path.join(OUTDIR, "left_vs_higher_ed_bottom30_income_2002_vs_2022.png")
fig.savefig(out, dpi=140)
print("saved", out)
for s in rows:
    print(s)
