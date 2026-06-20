#!/usr/bin/env Rscript
# run_all.R --------------------------------------------------------------
# End-to-end pipeline driver. Runs every stage in order.
#   Rscript run_all.R            # full build (Tier A + Tier B)
#   Rscript run_all.R tierA      # Tier A only (no large geo downloads needed)
#
# Prerequisites: see README.md (renv::restore() for packages; census/income/COG
# files placed in data/raw/census/ per R/01_download.R instructions).

args <- commandArgs(trailingOnly = TRUE)
mode <- if (length(args)) args[1] else "all"

source(here::here("R", "config.R"))

message("\n== 01 download ==");            source(here::here("R", "01_download.R")); download_elections()
if (mode == "all") download_contours()
download_historical_elections()   # CDSP 1988/1995 commune files
download_census()                 # INSEE census/income/COG + commune geometry (manifest-driven)

message("\n== 02 clean elections =="); source(here::here("R", "02_clean_elections.R"))
clean_votes_bv(); clean_turnout_bv(); clean_votes_commune()

message("\n== 03 clean census ==");    source(here::here("R", "03_clean_census.R"))
vmap <- readr::read_csv(file.path(PATHS$lookups, "census_vintage_map.csv"), show_col_types = FALSE)
for (v in unique(vmap$census_vintage)) build_census_vintage(v, "commune")
if (mode == "all") for (v in c(2012, 2017, 2021)) build_census_vintage(v, "iris")

message("\n== 06 build Tier A =="); source(here::here("R", "06_build_tierA_commune.R")); build_tierA()

if (mode == "all") {
  message("\n== 05 crosswalk bv =="); source(here::here("R", "05_crosswalk_bv.R")); crosswalk_bv_census()
  message("\n== 07 build Tier B =="); source(here::here("R", "07_build_tierB_bv.R")); build_tierB()
}

message("\nDone. Outputs in outputs/. See outputs/data_dictionary.md.")
