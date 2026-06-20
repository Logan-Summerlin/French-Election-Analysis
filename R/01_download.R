# 01_download.R ----------------------------------------------------------
# Fetch raw sources into data/raw/. Idempotent: skips files already present.
# Records provenance (URL + timestamp + size) to data/raw/_provenance.csv.
#
# Directly downloadable (stable object-storage URLs):
#   - election results (candidat + general parquet)   [sources 1-2]
#   - bureau de vote contours geojson                  [source 3]
#
# Census / income / COG (sources 4-7) use per-millesime INSEE archive URLs that
# are NOT stable across vintages. download_census_manual() prints the landing
# pages and the exact filenames the pipeline expects in data/raw/census/.

source(here::here("R", "config.R"))
suppressPackageStartupMessages({ library(curl); library(readr); library(dplyr) })

`%||%` <- function(a, b) if (is.null(a) || length(a) == 0) b else a

record_provenance <- function(name, url, dest) {
  prov_path <- file.path(PATHS$raw, "_provenance.csv")
  row <- tibble(
    name = name, url = url, dest = dest,
    bytes = if (file.exists(dest)) file.info(dest)$size else NA_real_,
    downloaded_at = as.character(Sys.time())
  )
  if (file.exists(prov_path)) {
    prev <- read_csv(prov_path, show_col_types = FALSE)
    row  <- bind_rows(filter(prev, name != !!name), row)
  }
  write_csv(row, prov_path)
}

download_one <- function(name, url, subdir = ".", overwrite = FALSE) {
  outdir <- file.path(PATHS$raw, subdir); dir.create(outdir, showWarnings = FALSE, recursive = TRUE)
  dest   <- file.path(outdir, basename(url))
  if (file.exists(dest) && !overwrite) {
    message(sprintf("[skip] %-22s already present (%s MB)", name,
                    round(file.info(dest)$size / 1e6, 1)))
  } else {
    message(sprintf("[get ] %-22s <- %s", name, url))
    # Retry with exponential backoff on transient network failures.
    for (attempt in 1:4) {
      ok <- tryCatch({ curl::curl_download(url, dest, quiet = FALSE, mode = "wb"); TRUE },
                     error = function(e) { message("  attempt ", attempt, " failed: ", conditionMessage(e)); FALSE })
      if (ok) break
      Sys.sleep(2 ^ attempt)
    }
  }
  record_provenance(name, url, dest)
  invisible(dest)
}

download_elections <- function(overwrite = FALSE) {
  download_one("elections_candidats", URLS$elections_candidats, "elections", overwrite)
  download_one("elections_general",   URLS$elections_general,   "elections", overwrite)
}

download_contours <- function(overwrite = FALSE) {
  # ~676 MB GeoJSON. Only needed for Tier B.
  download_one("bv_contours", URLS$bv_contours_geojson, "contours", overwrite)
}

# Census / income / COG: print instructions; these require picking the right
# millesime archive from the INSEE landing page (URLs rotate each release).
download_census_manual <- function() {
  msg <- c(
    "",
    "==== CENSUS / INCOME / COG: place files in data/raw/census/ ====",
    "INSEE archive URLs change each millesime, so resolve them from these pages:",
    sprintf("  IRIS census (CSP/diplome/pop): %s", URLS$census_iris_landing),
    sprintf("  Commune census (legal pop)   : %s", URLS$census_commune_landing),
    sprintf("  Filosofi IRIS income         : %s", URLS$filosofi_iris_landing),
    sprintf("  Filosofi 200m grid           : %s", URLS$filosofi_grid_landing),
    sprintf("  COG commune crosswalk        : %s", URLS$cog_landing),
    "",
    "Expected filenames (per vintage in census_vintage_map.csv), e.g.:",
    "  data/raw/census/base-ic-activite-residents-<YYYY>.csv     (CSP / activity, IRIS)",
    "  data/raw/census/base-ic-diplomes-formation-<YYYY>.csv     (education, IRIS)",
    "  data/raw/census/base-cc-evol-struct-pop-<YYYY>.csv        (population, commune)",
    "  data/raw/census/BTX_TD_FILO_DISP_IRIS_<YYYY>.csv          (Filosofi income, IRIS)",
    "  data/raw/census/Filosofi<YYYY>_carreaux_200m_met.gpkg     (Filosofi income grid)",
    "  data/raw/census/table-passage-communes-<YYYY>.csv         (COG crosswalk)",
    "  data/raw/census/communes-<GEO_REF_YEAR>.gpkg              (commune polygons, areas)",
    "================================================================", ""
  )
  cat(msg, sep = "\n")
}

if (sys.nframe() == 0) {
  download_elections()
  download_contours()    # comment out if only building Tier A
  download_census_manual()
}
