# French Election Analysis — Electoral Coalitions of the French Left (1988–2022)

A reproducible **R** pipeline that builds an analysis-ready dataset linking French
presidential election results to INSEE census and income data, so you can study how
the coalition of the French **Left** has changed across the **last 7 presidential
elections** (1988, 1995, 2002, 2007, 2012, 2017, 2022) as a function of **class,
population density, income, and education**.

## Two-tier design

| Tier | Unit | Elections | Purpose |
|------|------|-----------|---------|
| **A** | **commune** | all 7 (1988–2022) | consistent time-series backbone |
| **B** | **bureau de vote** (polling station) | 2002–2022 | fine within-city granularity |

Bureau-de-vote results exist in the open data only from **2002**; 1988 & 1995 are
commune-level only. Census attributes are attached to precincts by
**population-weighted dasymetric interpolation** using the INSEE Filosofi 200 m grid.

## Repository layout

```
R/                     pipeline stages (config + 01–08)
  config.R             paths, scope, verified source URLs
  01_download.R        fetch raw sources (idempotent, with provenance)
  02_clean_elections.R tidy long vote tables (bv + commune)
  03_clean_census.R    parse INSEE census + Filosofi -> tidy shares
  04_harmonize_communes.R  COG crosswalk to a fixed reference geography
  05_crosswalk_bv.R    census -> bureau de vote (dasymetric interpolation)
  06_build_tierA_commune.R   join votes + census -> commune panel
  07_build_tierB_bv.R  join bv votes + interpolated census
  08_left_classification.R   apply editable Left lookup -> families + total
run_all.R              end-to-end driver
data/lookups/          left_classification.csv, census_vintage_map.csv  (editable)
data/raw|interim|processed/   (gitignored; rebuilt by the pipeline)
outputs/               final datasets + data_dictionary.md
analysis/              example_left_by_class.R (demo regressions)
docs/                  data_sources.md, methodology.md, caveats.md
```

## Quick start

```r
# 1. install dependencies (listed in DESCRIPTION Imports)
install.packages(c("here","fs","curl","readr","dplyr","tidyr","stringr",
                   "stringi","purrr","arrow","sf","janitor"))
# optional: install.packages(c("areal","targets","ggplot2","broom"))
# to pin versions, run renv::init() then renv::snapshot() after install

# 2. Tier A only (no large geo downloads; commune panel for all 7 elections)
Rscript run_all.R tierA

# 3. Full build (adds Tier B: ~676 MB contours + Filosofi grid interpolation)
Rscript run_all.R
```

**All sources download automatically** — election results, bureau-de-vote contours,
the **historical 1988/1995 commune results** (CDSP), and **INSEE census, income, COG,
and commune geometry** — driven by `data/lookups/source_manifest.csv`
(`R/01_download.R` → `download_from_manifest()`). No manual file placement. A single
stale URL is logged and skipped rather than aborting the run; to add a census vintage,
append one manifest row. See **[docs/data_sources.md](docs/data_sources.md)**.

Two source limits to know (see [docs/caveats.md](docs/caveats.md)): the 1988/1995
commune files cover **only communes > 9 000 inhabitants** (flagged `coverage`), and
**1995 round 2** has no commune file.

## Defining "the Left" — fully editable

Every candidate's raw votes and vote share are preserved untouched. The Left
definition lives in **`data/lookups/left_classification.csv`**
(`year, nom, prenom, party, family, is_left`). Edit it — flip `is_left`, add a
candidate, change a `family` — and re-run; all aggregates (total-Left share and
per-family shares) re-derive automatically. Families:
`socialiste, communiste, ecologiste, gauche_radicale_LFI, extreme_gauche,
divers_gauche` (non-left rows carry `centre/droite/extreme_droite/souverainiste/divers`).

The default classification was **validated** against published national first-round
results (see [docs/methodology.md](docs/methodology.md)): reconstructed total-Left
shares reproduce the historical record to the decimal (e.g. 2012: 43.8%, 2022: 31.9%)
with 0 unmatched candidates.

## Outputs

- `outputs/tierA_commune_panel.(parquet|csv)` — long, per commune × year × round × candidate
- `outputs/tierA_commune_wide.(parquet|csv)` — per commune × year × round: Left aggregates + census
- `outputs/tierB_bureau_de_vote*.parquet` — same at bureau-de-vote level, 2002–2022
- `outputs/data_dictionary.md` — every column documented
- `outputs/candidate_landscapes/` — 2002 and 2022 first-round leading-candidate
  landscapes by median income and higher-education share, with full-sample and
  central-90% variants

**Scope:** Metropolitan France (mainland + Corsica). **Caveat:** these are
ecological (aggregate) relationships, not individual vote behavior — see
[docs/caveats.md](docs/caveats.md).
