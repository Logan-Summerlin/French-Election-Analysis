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

# --- Manifest-driven census / income / COG / historical-election fetch ----
# Replaces the old manual instructions. Driven by data/lookups/source_manifest.csv.
# Each row resolves to a URL by `source_type`:
#   datagouv_api : resolve the dataset slug via the data.gouv API, pick the
#                  resource whose filename/title matches `file_regex`.
#   insee_fichier: `locator` IS the full /fichier/<id>/<name>.zip URL.
#   direct       : plain URL.
# Robust by design: each row is HEAD-checked, retried with backoff, unzipped if
# flagged, and FAILURES ARE LOGGED AND SKIPPED so one stale URL never aborts the run.

resolve_datagouv <- function(slug, file_regex) {
  api <- sprintf("https://www.data.gouv.fr/api/1/datasets/%s/", slug)
  js  <- jsonlite::fromJSON(api, simplifyVector = FALSE)
  res <- js$resources
  url <- vapply(res, function(r) r$url %||% "", character(1))
  ttl <- vapply(res, function(r) r$title %||% "", character(1))
  key <- paste(basename(url), ttl)
  hit <- which(grepl(file_regex, key, ignore.case = TRUE, perl = TRUE))
  if (length(hit) == 0) stop("no resource matching /", file_regex, "/ in '", slug, "'")
  url[[hit[1]]]
}

unzip_if_needed <- function(path, dest_dir, do_unzip) {
  if (isTRUE(do_unzip) && grepl("\\.zip$", path, ignore.case = TRUE)) {
    tryCatch(utils::unzip(path, exdir = dest_dir, overwrite = TRUE),
             error = function(e) message("  unzip failed: ", conditionMessage(e)))
  }
}

download_from_manifest <- function(manifest = file.path(PATHS$lookups, "source_manifest.csv"),
                                   ids = NULL) {
  man <- readr::read_csv(manifest, show_col_types = FALSE)
  if (!is.null(ids)) man <- man[man$id %in% ids, ]
  for (i in seq_len(nrow(man))) {
    row <- man[i, ]
    url <- tryCatch(switch(row$source_type,
        datagouv_api  = resolve_datagouv(row$locator, row$file_regex),
        insee_fichier = row$locator,
        direct        = row$locator,
        stop("unknown source_type ", row$source_type)),
      error = function(e) { message("[resolve-fail] ", row$id, ": ", conditionMessage(e)); NA_character_ })
    if (is.na(url)) next

    dest_dir <- file.path(PATHS$raw, row$dest_subdir); dir.create(dest_dir, recursive = TRUE, showWarnings = FALSE)
    dest <- file.path(dest_dir, basename(url))
    if (file.exists(dest) && file.info(dest)$size > 0) {
      message(sprintf("[skip] %-22s present", row$id))
    } else {
      message(sprintf("[get ] %-22s <- %s", row$id, url))
      ok <- FALSE
      for (attempt in 1:4) {
        ok <- tryCatch({ curl::curl_download(url, dest, quiet = TRUE, mode = "wb"); TRUE },
                       error = function(e) { message("  attempt ", attempt, " failed: ", conditionMessage(e)); FALSE })
        if (ok) break
        Sys.sleep(2 ^ attempt)
      }
      if (!ok) { message("[FAIL] ", row$id, " — left for manual download"); next }
    }
    unzip_if_needed(dest, dest_dir, row$unzip)
    record_provenance(row$id, url, dest)
  }
  invisible(man)
}

# Convenience wrappers used by run_all.R.
download_historical_elections <- function()
  download_from_manifest(ids = c("elec_1988_t1", "elec_1988_t2", "elec_1995_t1"))

download_census <- function()
  download_from_manifest(ids = c("cog_passage",
    "census_act_iris_2012","census_act_iris_2017","census_act_iris_2021",
    "census_dip_iris_2021","census_dip_com_2012","census_dip_com_2017",
    "income_filo_iris_2021","commune_geo","filo_grid_2019"))

if (sys.nframe() == 0) {
  download_elections()
  download_contours()    # comment out if only building Tier A
  download_historical_elections()
  download_census()
}
