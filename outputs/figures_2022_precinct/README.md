# Precinct-level scatter plots — 2022 Left vote vs socioeconomic characteristics

Scatter plots (with **OLS** and **LOWESS** trend lines) of the **Left first-round
vote share** (Y) against socioeconomic characteristics (X) at the **bureau de vote
/ precinct** level, 2022 presidential election, round 1, metropolitan France
(n ≈ 67,000 precincts).

## Figures
- `left_vs_socioeconomic_grid_2022.png` — all seven variables in one panel
- `left_vs_pop_density.png` — population density (log X)
- `left_vs_median_income.png` — median disposable income
- `left_vs_csp_cadres_pct.png` — managers / higher professions (cadres)
- `left_vs_csp_ouvriers_pct.png` — manual workers (ouvriers)
- `left_vs_csp_employes_pct.png` — clerical & service workers (employés)
- `left_vs_higher_ed_pct.png` — higher-education graduates
- `left_vs_no_diploma_pct.png` — no / low diploma

## What "Left" means
Sum of the six Left candidates in `data/lookups/left_classification.csv` for 2022
(`is_left == 1`): **Mélenchon, Jadot, Roussel, Hidalgo, Poutou, Arthaud**. The
reconstructed national first-round Left share is **31.9%**, matching the published
record (and the repository's Tier A validation).

## Granularity caveat
The **vote share is genuinely at the precinct level**. The socioeconomic **X**
attributes are **commune-level** (INSEE 2021 census + Filosofi) attached to every
precinct of that commune — the lighter alternative to the repository's full
**Tier B dasymetric interpolation** (which requires the ~676 MB bureau-de-vote
contour layer and the Filosofi 200 m grid). Large cities are split into
arrondissement-communes (Paris, Lyon, Marseille), so an urban gradient is still
visible, but within-commune variation in X is not resolved. These are
**ecological** (aggregate) relationships, not individual vote behaviour — see
`docs/caveats.md`.

## Headline patterns (round 1, 2022)
| X variable | Pearson r with Left share |
|---|---|
| Population density (log) | **+0.50** |
| Higher-education graduates | +0.25 |
| Managers / cadres | +0.24 |
| Clerical / employés | +0.11 |
| No / low diploma | +0.09 |
| Manual workers / ouvriers | −0.23 |
| Median income | −0.25 |

The Left in 2022 is strongest in **dense, lower-income, educationally-mixed urban**
precincts — the Mélenchon/LFI metropolitan signature — and the classic *ouvrier*
correlation has gone negative, consistent with the recomposition of the Left
coalition.

## Low-income subset & 2002↔2022 comparison
- `left_vs_higher_ed_bottom30_income_2022.png` — 2022 Left vote vs higher education,
  restricted to the **bottom 30% of precincts by commune median income** (≤ €21,270;
  n=18,818). Even among the poorest precincts the gradient is positive (r=+0.45).
- `left_vs_higher_ed_bottom30_income_2002_vs_2022.png` — **side-by-side** of the same
  analysis for **2002 vs 2022**. Each election is paired with the **nearest-available
  INSEE census/Filosofi vintage** (Filosofi income does not exist before 2012):
  **2002 → 2012 census**, **2022 → 2021 census**. Both the income filter and the
  higher-education X axis use that election's vintage.

  | election (census) | n | r | OLS slope | weighted Left |
  |---|---|---|---|---|
  | 2002 (2012) | 17,588 | +0.21 | +0.11 pp / +1pp | 43.9% |
  | 2022 (2021) | 18,818 | +0.45 | +0.74 pp / +1pp | 35.8% |

  Among low-income precincts the Left–education link is **much steeper in 2022 than in
  2002**: in 2002 the Left was broad-based across education levels (flat, weak gradient),
  whereas by 2022 the Left vote in poor precincts is markedly concentrated in the more
  educated ones — the metropolitan, graduate-leaning recomposition of the Left.

  Higher-education definition by vintage (both = "Bac+2 and above" / non-schooled 15+):
  2012 = `(P12_NSCOL15P_BACP2 + P12_NSCOL15P_SUP) / P12_NSCOL15P`;
  2021 = `(P21_NSCOL15P_SUP2 + P21_NSCOL15P_SUP34 + P21_NSCOL15P_SUP5) / P21_NSCOL15P`.

## Reproduce
```bash
python3 analysis/build_bv_2022_dataset.py            # downloads sources -> data/processed/bv_2022_analysis.parquet
python3 analysis/scatter_left_vs_socioeconomic_2022.py   # -> these PNGs
```
Dependencies: `pandas pyarrow numpy scipy statsmodels matplotlib geopandas`.
