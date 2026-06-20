# config.R ---------------------------------------------------------------
# Central configuration: paths, source URLs, constants.
# Sourced by every pipeline script. No side effects beyond defining objects.

suppressPackageStartupMessages({
  library(here)
  library(fs)
})

# --- Project paths -------------------------------------------------------
PATHS <- list(
  raw       = here("data", "raw"),
  interim   = here("data", "interim"),
  processed = here("data", "processed"),
  lookups   = here("data", "lookups"),
  outputs   = here("outputs")
)
invisible(lapply(PATHS, dir_create))

# --- Scope ---------------------------------------------------------------
# The 7 presidential elections in scope.
ELECTION_YEARS <- c(1988, 1995, 2002, 2007, 2012, 2017, 2022)

# Bureau-de-vote-level results exist in the aggregated open dataset only from 2002.
BV_YEARS <- c(2002, 2007, 2012, 2017, 2022)

# Metropolitan France: departement codes are 01..95 plus 2A/2B (Corsica).
# Overseas (DOM) start with 97/98 and are EXCLUDED per project scope.
is_metropolitan <- function(code_departement) {
  cd <- toupper(trimws(code_departement))
  !grepl("^9[78]", cd) & !grepl("^98", cd) & nchar(cd) <= 3
}

# Reference geography year for commune harmonization (COG).
GEO_REF_YEAR <- 2022L

# --- Source URLs (verified against data.gouv.fr API, June 2026) -----------
URLS <- list(
  # 1. Aggregated election results (Ministry of Interior, via data.gouv.fr).
  #    Bureau-de-vote level, presidential rounds tagged e.g. "2022_pres_t1".
  elections_candidats = "https://object.files.data.gouv.fr/data-pipeline-open/elections/candidats_results.parquet",
  elections_general   = "https://object.files.data.gouv.fr/data-pipeline-open/elections/general_results.parquet",
  elections_nuances   = "https://object.files.data.gouv.fr/data-pipeline-open/elections/general_results.parquet", # nuance dict is in candidats file

  # 3. Bureau de vote contours (polygons), INSEE/Etalab method, ~2022 vintage.
  bv_contours_geojson = "https://object.files.data.gouv.fr/data-pipeline-open/reu/contours-france-entiere-latest-v2.geojson",

  # NOTE on census / income (sources 4-6): INSEE distributes these as per-vintage
  # zipped CSV/xlsx with non-stable archive URLs that change with each millesime.
  # They are resolved at download time from the dataset landing pages below
  # (see R/01_download.R, function download_census_manual()).
  census_iris_landing   = "https://www.insee.fr/fr/statistiques/7704076",   # Bases infracommunales IRIS (update each run)
  census_commune_landing= "https://www.insee.fr/fr/statistiques/8268806",   # Population legale / RP commune
  filosofi_iris_landing = "https://www.insee.fr/fr/statistiques/8229323",   # Revenus pauvrete niveau de vie IRIS
  filosofi_grid_landing = "https://www.data.gouv.fr/datasets/revenus-pauvrete-et-niveau-de-vie-donnees-carroyees-2019-et-2021-dispositif-fichier-localise-social-et-fiscal-filosofi",
  cog_landing           = "https://www.insee.fr/fr/information/8377162"     # Code Officiel Geographique (commune crosswalk)
)

# Coordinate reference system for all geographic operations: RGF93 / Lambert-93.
CRS_LAMBERT93 <- 2154

message("config.R loaded. ", length(ELECTION_YEARS), " elections in scope; ",
        "geo reference year = ", GEO_REF_YEAR, ".")
