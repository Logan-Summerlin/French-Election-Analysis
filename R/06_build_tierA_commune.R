# 06_build_tierA_commune.R -----------------------------------------------
# Tier A: the consistent commune-level panel across all 7 elections.
# Joins commune votes + Left classification + nearest-vintage census, all
# harmonized to GEO_REF_YEAR.
#
# Outputs:
#   outputs/tierA_commune_panel.parquet  (long: one row per commune x year x round x candidate)
#   outputs/tierA_commune_wide.parquet   (one row per commune x year x round: Left aggregates + census)

source(here::here("R", "config.R"))
source(here::here("R", "04_harmonize_communes.R"))
source(here::here("R", "08_left_classification.R"))
suppressPackageStartupMessages({ library(dplyr); library(readr); library(arrow); library(stringr) })

build_tierA <- function() {
  vmap   <- read_csv(file.path(PATHS$lookups, "census_vintage_map.csv"), show_col_types = FALSE)
  votes  <- arrow::read_parquet(file.path(PATHS$interim, "votes_commune.parquet"))
  xw     <- load_cog_crosswalk()

  # Harmonize commune codes, then classify candidates.
  votes <- remap_commune(votes, "code_commune", xw,
                         value_cols = "voix",
                         group_extra = c("year", "round", "nom", "prenom", "nom_norm"))
  classified <- classify_votes(votes)

  # Turnout (exprimes) per commune for shares — aggregate bv turnout up.
  turnout <- arrow::read_parquet(file.path(PATHS$interim, "turnout_bv.parquet")) |>
    group_by(code_commune, year, round) |>
    summarise(inscrits = sum(inscrits, na.rm = TRUE), votants = sum(votants, na.rm = TRUE),
              exprimes = sum(exprimes, na.rm = TRUE), .groups = "drop") |>
    remap_commune("code_commune", xw, value_cols = c("inscrits","votants","exprimes"),
                  group_extra = c("year","round")) |>
    mutate(abstention_rate = 1 - votants / inscrits)

  # --- LONG panel: per-candidate votes + share + classification ----------
  long <- classified |>
    left_join(select(turnout, code_commune, year, round, inscrits, votants, exprimes),
              by = c("code_commune", "year", "round")) |>
    mutate(share = 100 * voix / exprimes)

  # --- Census join (nearest vintage per election year) -------------------
  census_for_year <- function(y) {
    v <- vmap$census_vintage[vmap$election_year == y]
    f <- file.path(PATHS$interim, str_glue("census_commune_{v}.parquet"))
    if (!file.exists(f)) return(NULL)
    arrow::read_parquet(f) |>
      remap_commune_census(xw) |>
      mutate(year = y, census_vintage = v)
  }
  census <- purrr::map_dfr(ELECTION_YEARS, census_for_year)

  long <- long |> left_join(census, by = c("code_commune" = "geo_id", "year"))
  write_parquet(long, file.path(PATHS$outputs, "tierA_commune_panel.parquet"))
  write_csv(long, file.path(PATHS$outputs, "tierA_commune_panel.csv"))

  # --- WIDE: Left aggregates + census, one row per commune x year x round -
  agg  <- compute_left_aggregates(classified |>
            left_join(select(turnout, code_commune, year, round, exprimes),
                      by = c("code_commune","year","round")),
            unit_cols = "code_commune")
  wide <- agg |>
    left_join(turnout, by = c("code_commune","year","round")) |>
    left_join(census, by = c("code_commune" = "geo_id", "year"))
  write_parquet(wide, file.path(PATHS$outputs, "tierA_commune_wide.parquet"))
  write_csv(wide, file.path(PATHS$outputs, "tierA_commune_wide.csv"))

  message("Tier A built: ", nrow(long), " candidate-rows; ", nrow(wide), " unit-rows.")
  invisible(list(long = long, wide = wide))
}

# Census tables are shares + a population weight; harmonize accordingly.
remap_commune_census <- function(df, xw) {
  share_cols <- str_subset(names(df), "_pct$|median_income")
  remap_commune(rename(df, code_commune = geo_id), "code_commune", xw,
                value_cols = intersect("pop_15plus", names(df)),
                share_cols = share_cols,
                weight_col = if ("pop_15plus" %in% names(df)) "pop_15plus" else NULL) |>
    rename(geo_id = code_commune)
}

if (sys.nframe() == 0) build_tierA()
