# 07_build_tierB_bv.R ----------------------------------------------------
# Tier B: fine-grained bureau-de-vote cross-section for 2002-2022.
# Joins bv votes + turnout + Left classification + interpolated census
# (from 05_crosswalk_bv.R).
#
# Outputs:
#   outputs/tierB_bureau_de_vote.parquet  (long: per bv x year x round x candidate)
#   outputs/tierB_bureau_de_vote_wide.parquet (per bv x year x round: Left aggregates + census)

source(here::here("R", "config.R"))
source(here::here("R", "08_left_classification.R"))
suppressPackageStartupMessages({ library(dplyr); library(readr); library(arrow); library(stringr) })

build_tierB <- function() {
  votes   <- arrow::read_parquet(file.path(PATHS$interim, "votes_bv.parquet"))
  turnout <- arrow::read_parquet(file.path(PATHS$interim, "turnout_bv.parquet")) |>
    select(bv_id, code_commune, year, round, inscrits, votants, exprimes, abstention_rate)
  bvc_path <- file.path(PATHS$processed, "bv_census.parquet")
  bv_census <- if (file.exists(bvc_path)) arrow::read_parquet(bvc_path) else {
    message("[note] bv_census.parquet missing; run 05_crosswalk_bv.R. ",
            "Building Tier B votes without census attributes.")
    NULL
  }

  classified <- classify_votes(votes)

  long <- classified |>
    left_join(turnout, by = c("bv_id", "year", "round")) |>
    mutate(share = 100 * voix / exprimes)
  if (!is.null(bv_census)) long <- long |> left_join(bv_census, by = "bv_id")

  write_parquet(long, file.path(PATHS$outputs, "tierB_bureau_de_vote.parquet"))

  agg <- compute_left_aggregates(
    classified |> left_join(select(turnout, bv_id, year, round, exprimes),
                            by = c("bv_id","year","round")),
    unit_cols = "bv_id")
  wide <- agg |>
    left_join(turnout, by = c("bv_id","year","round"))
  if (!is.null(bv_census)) wide <- wide |> left_join(bv_census, by = "bv_id")
  write_parquet(wide, file.path(PATHS$outputs, "tierB_bureau_de_vote_wide.parquet"))

  message("Tier B built: ", nrow(long), " candidate-rows; ", nrow(wide), " bv-rows.")
  invisible(list(long = long, wide = wide))
}

if (sys.nframe() == 0) build_tierB()
