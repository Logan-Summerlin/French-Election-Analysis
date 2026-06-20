# Methodology

## Objective

Build a dataset to study how the **socioeconomic coalition of the French Left**
changed across the last 7 presidential elections (1988–2022), relating Left support
to **class (CSP), population density, income, and education**.

## Unit-of-analysis problem and the two-tier solution

Voting and census data live on incompatible geographies, and granularity degrades
backward in time:

- **Bureau de vote** (polling station, ~70 000 units) — finest voting unit, but
  open results only from **2002**, and boundary polygons only as a single ~2022
  vintage.
- **Commune** (~35 000 units) — consistent voting unit across all 7 elections; census
  published here for every vintage.
- Census geographies (IRIS, 200 m grid) never align with polling-station boundaries.

We therefore build **two tiers**:

- **Tier A (commune, 1988–2022)** — the authoritative time series. Bureau-de-vote
  results aggregated to commune; 1988/1995 ingested directly at commune level.
- **Tier B (bureau de vote, 2002–2022)** — fine within-city detail where data allows.

## Temporal harmonization (Tier A)

Communes merge/split over 34 years. Before any census join, all commune codes are
remapped to a fixed reference geography (`GEO_REF_YEAR = 2022`) using the INSEE COG
passage table (`R/04_harmonize_communes.R`). Vote counts are summed across merged
codes; census **shares** are recombined as population-weighted means.

## Census → precinct linkage (Tier B): population-weighted dasymetric interpolation

Census attributes are pushed onto bureau-de-vote polygons using the Filosofi **200 m
grid** as a dasymetric weight layer (`R/05_crosswalk_bv.R`):

1. Each 200 m grid cell carries `{population, median income}`.
2. Spatial join cell → IRIS gives the cell its IRIS-level **shares** (CSP, education).
3. Spatial join cell → bureau-de-vote polygon assigns the cell to a precinct.
4. Per precinct: **population-weighted mean** of shares and income; summed population;
   density = population / polygon area.

Weighting by where people live (grid population), not raw area, is what makes this
*dasymetric* rather than naive areal interpolation — essential in communes mixing
dense housing with empty land.

## Census-vintage matching

Each election is joined to the nearest available census/income vintage
(`data/lookups/census_vintage_map.csv`): e.g. 1988→RP1990, 1995→RP1999, 2002→RP1999,
2007→RP2006, 2012→2012, 2017→2017, 2022→2021. The exact vintage is recorded per row
(`census_vintage`).

## Defining and aggregating the Left

`data/lookups/left_classification.csv` assigns every candidate a `family` and
`is_left` flag, keyed on `(year, surname)` because `nuance` is missing for 2017/2022.
Derived per unit/year/round:

- `total_left_share` = Σ(left candidate votes) / exprimés × 100
- `left_<family>_share` for each left family (socialiste, communiste, ecologiste,
  gauche_radicale_LFI, extreme_gauche, divers_gauche)

The lookup is the single point of control: editing it re-derives all aggregates.

### Validation of the default classification

Reconstructed national first-round total-Left share (built directly from the source
parquet via the lookup join) vs. the published historical record:

| Election | Reconstructed Left (t1) | Unmatched candidates |
|----------|------------------------:|---------------------:|
| 2002 | 42.93 % | 0 |
| 2007 | 36.41 % | 0 |
| 2012 | 43.75 % | 0 |
| 2017 | 27.68 % | 0 |
| 2022 | 31.95 % | 0 |

(2002 includes Chevènement as `divers_gauche`; flip `is_left` in the CSV to exclude.)
These match published results to the decimal, confirming the surname-keyed join and
the classification.

## Recommended analyses

- **Trend**: registered-voter-weighted total-Left share by year.
- **Gradients**: Left share by density / income / education / CSP quintile per year.
- **Cross-sectional OLS** per election: `total_left_share ~ log(density) + csp_* +
  higher_ed_pct + median_income`, weighted by registered voters.
- **Coalition recomposition**: per-family shares over time (PCF decline, PS collapse
  2017, LFI rise). See `analysis/example_left_by_class.R`.
