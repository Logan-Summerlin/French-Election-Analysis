# _targets.R -------------------------------------------------------------
# Optional {targets} orchestration mirroring run_all.R. Run with:
#   targets::tar_make()
# Prefer run_all.R for a simple linear build; use this for cached re-runs.

library(targets)
source(here::here("R", "config.R"))
for (f in c("01_download","02_clean_elections","03_clean_census",
            "04_harmonize_communes","05_crosswalk_bv",
            "06_build_tierA_commune","07_build_tierB_bv","08_left_classification"))
  source(here::here("R", paste0(f, ".R")))

tar_option_set(packages = c("dplyr","readr","stringr","stringi","arrow","sf","purrr","tidyr"))

list(
  tar_target(dl_elections,  download_elections(),         format = "file"),
  tar_target(votes_bv,      { dl_elections; clean_votes_bv() }),
  tar_target(turnout_bv,    { dl_elections; clean_turnout_bv() }),
  tar_target(votes_commune, { votes_bv;     clean_votes_commune() }),
  tar_target(census_communes,
             { vmap <- readr::read_csv(file.path(PATHS$lookups,"census_vintage_map.csv"),
                                       show_col_types = FALSE)
               lapply(unique(vmap$census_vintage), build_census_vintage, geo = "commune") }),
  tar_target(tierA, { votes_commune; census_communes; build_tierA() }),
  tar_target(bv_census, { download_contours(); crosswalk_bv_census() }),
  tar_target(tierB, { votes_bv; turnout_bv; bv_census; build_tierB() })
)
