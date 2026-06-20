# 02_clean_elections.R ---------------------------------------------------
# Parse raw election parquet into tidy long tables of votes.
# Produces:
#   data/interim/votes_bv.parquet      one row per (year,round,bv,candidate)   [2002-2022]
#   data/interim/turnout_bv.parquet    one row per (year,round,bv)             [2002-2022]
#   data/interim/votes_commune.parquet votes aggregated to commune, ALL years where available
#
# 1988 & 1995 are NOT in the open aggregated dataset. read_historical_commune()
# ingests a user-supplied commune-level CSV (Ministry of Interior / CDSP archive)
# placed at data/raw/elections/historical_<year>.csv with columns:
#   code_commune, nom, prenom, voix, inscrits, votants, exprimes  (+ year, round)

source(here::here("R", "config.R"))
suppressPackageStartupMessages({
  library(arrow); library(dplyr); library(stringr); library(stringi); library(readr)
})

norm_name <- function(x) stri_trans_general(toupper(trimws(x)), "Latin-ASCII")
year_of   <- function(id_election) as.integer(str_sub(id_election, 1, 4))
round_of  <- function(id_election) as.integer(str_extract(id_election, "(?<=_t)\\d"))

# --- Bureau-de-vote level votes (2002-2022) ------------------------------
clean_votes_bv <- function() {
  cand <- open_dataset(file.path(PATHS$raw, "elections", "candidats_results.parquet")) |>
    filter(str_detect(id_election, "_pres_t")) |>
    select(id_election, code_departement, code_commune, code_bv,
           nuance, nom, prenom, voix) |>
    collect()

  cand <- cand |>
    mutate(year = year_of(id_election), round = round_of(id_election),
           bv_id = str_c(code_commune, "_", code_bv),
           nom_norm = norm_name(nom)) |>
    filter(is_metropolitan(code_departement)) |>
    select(year, round, code_departement, code_commune, bv_id,
           nuance, nom, prenom, nom_norm, voix)

  write_parquet(cand, file.path(PATHS$interim, "votes_bv.parquet"))
  message("votes_bv: ", nrow(cand), " rows, years ",
          paste(sort(unique(cand$year)), collapse = ","))
  invisible(cand)
}

# --- Bureau-de-vote turnout (inscrits/votants/exprimes) ------------------
clean_turnout_bv <- function() {
  gen <- open_dataset(file.path(PATHS$raw, "elections", "general_results.parquet")) |>
    filter(str_detect(id_election, "_pres_t")) |>
    select(id_election, code_departement, code_commune, code_bv,
           inscrits, votants, abstentions, blancs, nuls, exprimes) |>
    collect()

  gen <- gen |>
    mutate(year = year_of(id_election), round = round_of(id_election),
           bv_id = str_c(code_commune, "_", code_bv)) |>
    filter(is_metropolitan(code_departement)) |>
    mutate(abstention_rate = abstentions / inscrits) |>
    select(year, round, code_departement, code_commune, bv_id,
           inscrits, votants, abstentions, blancs, nuls, exprimes, abstention_rate)

  write_parquet(gen, file.path(PATHS$interim, "turnout_bv.parquet"))
  message("turnout_bv: ", nrow(gen), " rows")
  invisible(gen)
}

# --- Historical commune-level results (1988, 1995) -----------------------
read_historical_commune <- function() {
  files <- list.files(file.path(PATHS$raw, "elections"),
                      pattern = "^historical_\\d{4}\\.csv$", full.names = TRUE)
  if (length(files) == 0) {
    message("[note] No historical_<year>.csv found for 1988/1995. ",
            "See docs/data_sources.md to obtain CDSP/Ministry archives.")
    return(tibble())
  }
  purrr::map_dfr(files, function(f) {
    read_csv(f, show_col_types = FALSE) |>
      mutate(code_commune = str_pad(as.character(code_commune), 5, pad = "0"),
             nom_norm = norm_name(nom))
  })
}

# --- Aggregate everything to commune level (all 7 years) -----------------
clean_votes_commune <- function() {
  bv <- arrow::read_parquet(file.path(PATHS$interim, "votes_bv.parquet"))
  bv_commune <- bv |>
    group_by(year, round, code_departement, code_commune, nom, prenom, nom_norm) |>
    summarise(voix = sum(voix, na.rm = TRUE), .groups = "drop")

  hist <- read_historical_commune()
  commune <- bind_rows(bv_commune, hist) |>
    filter(year %in% ELECTION_YEARS)

  write_parquet(commune, file.path(PATHS$interim, "votes_commune.parquet"))
  message("votes_commune: ", nrow(commune), " rows, years ",
          paste(sort(unique(commune$year)), collapse = ","))
  invisible(commune)
}

if (sys.nframe() == 0) {
  clean_votes_bv()
  clean_turnout_bv()
  clean_votes_commune()
}
