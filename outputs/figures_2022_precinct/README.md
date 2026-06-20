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

## Reproduce
```bash
python3 analysis/build_bv_2022_dataset.py            # downloads sources -> data/processed/bv_2022_analysis.parquet
python3 analysis/scatter_left_vs_socioeconomic_2022.py   # -> these PNGs
```
Dependencies: `pandas pyarrow numpy scipy statsmodels matplotlib geopandas`.
