# Data sources

All sources are open and free. URLs verified against the data.gouv.fr / INSEE
catalogues in June 2026.

## 1–2. Election results (Ministry of the Interior, via data.gouv.fr)

Dataset: **"Données des élections agrégées"**
(`https://www.data.gouv.fr/datasets/donnees-des-elections-agregees`).

| File | URL | Level | Size |
|------|-----|-------|------|
| Résultats par candidat (parquet) | `https://object.files.data.gouv.fr/data-pipeline-open/elections/candidats_results.parquet` | bureau de vote | ~161 MB |
| Résultats généraux (parquet) | `https://object.files.data.gouv.fr/data-pipeline-open/elections/general_results.parquet` | bureau de vote | ~71 MB |

Election rows are keyed `id_election = "<year>_pres_t<round>"`. **Presidential
coverage at bureau-de-vote level (confirmed by querying the parquet):**
`2002, 2007, 2012, 2017, 2022` (both rounds). Candidate-level fields:
`nuance, nom, prenom, voix, ratio_voix_exprimes`. Turnout fields (general file):
`inscrits, votants, abstentions, blancs, nuls, exprimes`.
**Note:** `nuance` is empty for 2017 & 2022 → the Left lookup keys on surname.

### 1988 & 1995 (not in the open aggregated dataset)
Obtain commune-level results from one of:
- **CDSP / Sciences Po** election data archive (`data.sciencespo.fr`).
- Ministry of the Interior historical archives
  (`elections.interieur.gouv.fr/resultats-de-toutes-elections`).
Place as `data/raw/elections/historical_1988.csv` / `historical_1995.csv` with
columns `code_commune, nom, prenom, voix, inscrits, votants, exprimes, year, round`.
`R/02_clean_elections.R::read_historical_commune()` ingests them.

## 3. Bureau de vote contours (polygons)

Dataset: **"Proposition de contours des bureaux de vote"**
(`https://www.data.gouv.fr/datasets/proposition-de-contours-des-bureaux-de-vote`),
generated from the Répertoire Électoral Unique by Etalab/INSEE (`InseeFrLab/mapvotr`,
`etalab/bureau-vote`).

- GeoJSON: `https://object.files.data.gouv.fr/data-pipeline-open/reu/contours-france-entiere-latest-v2.geojson` (~676 MB)

Single **~2022 vintage**; approximate (see caveats).

## 4. Census — population, CSP (class), education (INSEE)

- **IRIS infracommunal databases** ("Bases de données infracommunales à l'IRIS"):
  activity/CSP, diplômes/formation, population, housing.
  `https://www.insee.fr/fr/statistiques/7704076` (millésime updates each year).
- **Commune-level census** (population, structure): historical RP 1982/1990/1999 and
  annual millésimes from 2006. `https://www.insee.fr/fr/statistiques/8268806`.
- CSP coded `CS1..CS8`; education series `NSCOL15P_*`.

## 5. Income — INSEE Filosofi

- **IRIS income** ("Revenus, pauvreté et niveau de vie", IRIS):
  `https://www.insee.fr/fr/statistiques/8229323` (communes ≥ 5 000 inhab.).
- **200 m grid** (carreaux), population + income, used as the dasymetric weight
  layer: `https://www.data.gouv.fr/datasets/revenus-pauvrete-et-niveau-de-vie-donnees-carroyees-2019-et-2021-dispositif-fichier-localise-social-et-fiscal-filosofi`.
- Filosofi millésimes: 2012 → 2021. Earlier income (DGFiP Revenus Fiscaux Localisés)
  ~2001+, sparse. **Weakest historical coverage** — no localized income pre-2002.

## 6. Geographies / areas

- IGN **ADMIN-EXPRESS** commune polygons (for area → density) and IRIS contours.
  `https://geoservices.ign.fr/adminexpress`.

## 7. Commune crosswalk over time — INSEE COG

- **Code Officiel Géographique** "communes nouvelles" passage table, to harmonize
  commune codes 1988→2022 (merges/splits/renumbering).
  `https://www.insee.fr/fr/information/8377162`.

## Vintage matching

`data/lookups/census_vintage_map.csv` maps each election year to its nearest census
& income vintage (e.g. 1988→RP1990, 2002→RP1999, 2017→RP2017+Filosofi2017,
2022→RP2021+Filosofi2021).
