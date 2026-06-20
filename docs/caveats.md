# Caveats and limitations

Read before drawing conclusions.

## 1. Ecological inference fallacy
Every relationship in this dataset is **aggregate** (commune or precinct), not
individual. "Left share is higher where there are more manual workers" does **not**
prove manual workers vote Left. Frame findings as area-level associations; if you
need individual-level inference, pair this with survey data or use ecological-
inference models (e.g. `eiPack`, `ei`) and report their assumptions.

## 2. Bureau-de-vote contours are approximate (Tier B)
The polygons are a **single ~2022 vintage**, reconstructed from voter addresses by an
INSEE/Etalab heuristic — not authoritative legal boundaries. Applying them to 2002–
2017 assumes boundaries were roughly stable; precinct splits/merges over that span add
error. **Tier A (commune) is the authoritative time series.** Treat Tier B pre-2022
census attributes as estimates.

## 3. Interpolation error
Population-weighted dasymetric interpolation still smooths sharp socioeconomic
boundaries and inherits Filosofi's confidentiality imputation (cells with <11 fiscal
households are imputed; flagged upstream by INSEE's `I_est_cr`). `interp_quality_flag`
marks precincts with sparse/missing income.

## 4. Income coverage is thin before 2012
Localized income (Filosofi) begins 2012; DGFiP Revenus Fiscaux Localisés (~2001+) is
coarser and sparse. **1988 & 1995 have no localized income** — those `median_income`
cells are NA by construction. Filosofi IRIS income is also absent in communes
< 5 000 inhabitants. Don't over-interpret income for rural/early observations.

## 5. Census vintage ≠ election year
Census is matched to the nearest vintage (up to several years off, especially the
1990/1999 general censuses against 1988/1995/2002). Socioeconomic structure is slow-
moving but not constant; the actual vintage is recorded per row (`census_vintage`).

## 6. Commune boundary changes
Harmonization to 2022 geography handles merges well and splits crudely (rare;
left ~1:1). Residual mismatches are logged at build time. A handful of communes
(notably Paris/Lyon/Marseille arrondissements vs. commune coding) need care when
joining — verify the `code_commune` convention matches between sources.

## 7. "Left" is a modelling choice
The default `left_classification.csv` makes defensible but contestable calls
(e.g. Chevènement 2002 as `divers_gauche`; ecologists counted as Left throughout;
Mélenchon's `Front de Gauche` 2012 vs `LFI` 2017/2022). These materially affect totals
— treat the lookup as a parameter and run sensitivity checks by editing it.

## 8. 1988 & 1995 commune coverage is urban-biased
The only openly-automatable commune source for these years (CDSP "1965-2012")
covers **communes > 9 000 inhabitants only**, and **1995 round 2 has no commune
file at all**. So 1988/1995 Tier A rows are flagged `coverage = "communes_gt_9000"`
and skew urban; the 1995 second round is absent. Filter on `coverage` when comparing
across years, and treat early-year socioeconomic gradients with caution. Full-coverage
data needs a registered CDSP download (not automatable).

## 9. Population density is an adult-population proxy
`pop_density` is computed as census **population 15+** (`pop_15plus`) divided by
commune area (km², from the france-geojson commune polygons), not total population.
The two correlate > 0.98, but the level is biased low where the under-15 share is
high. Swap in INSEE legal total population for an exact figure if needed.

## 10. Scope
Metropolitan France only (mainland + Corsica). Overseas departments are excluded;
their distinct census coverage and voting patterns would need separate handling.
