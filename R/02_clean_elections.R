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
# Parses the CDSP "communes >9000 inhab" files downloaded by 01_download.R:
#   cdsp_presi1988t1_commp9000.csv, cdsp_presi1988t2_commp9000.csv,
#   cdsp_presi1995t1_commp9000.csv
# Format (confirmed): comma-separated UTF-8, wide, columns:
#   Code departement, departement, numero commune, commune, Inscrits, Votants,
#   Exprimes, <one column per candidate named "SURNAME (PARTY)" or "SURNAME">.
# We melt candidate columns to long; the candidate SURNAME feeds the existing
# Left lookup join in R/08. Coverage flagged "communes_gt_9000" (urban-biased).
# 1995 round 2 has no commune file -> absent by construction.

# Build a 5-char INSEE commune code from department + sequential commune number.
make_commune_code <- function(dep, num) {
  dep <- toupper(trimws(dep))
  dep <- ifelse(grepl("^[0-9]+$", dep), formatC(as.integer(dep), width = 2, flag = "0"), dep)
  paste0(dep, formatC(as.integer(num), width = 3, flag = "0"))
}

parse_cdsp_commune <- function(path) {
  m <- regmatches(basename(path), regexec("presi(\\d{4})t(\\d)", basename(path)))[[1]]
  yr <- as.integer(m[2]); rd <- as.integer(m[3])
  raw <- read_delim(path, delim = ",", show_col_types = FALSE,
                    locale = locale(encoding = "UTF-8"),
                    col_types = cols(.default = col_character()))
  hdr  <- names(raw)
  nh   <- tolower(stri_trans_general(hdr, "Latin-ASCII"))
  dep_col  <- hdr[nh == "code departement"][1]
  num_col  <- hdr[nh %in% c("numero commune", "no commune")][1]
  id_set   <- c("code departement","departement","numero commune","no commune",
                "commune","inscrits","votants","exprimes")
  cand_cols <- hdr[!(nh %in% id_set) & nzchar(hdr) & !grepl("^\\.{3}", hdr)]
  cand_cols <- cand_cols[colSums(!is.na(raw[cand_cols])) > 0]   # drop all-empty trailers
  surname   <- trimws(sub("\\s*\\(.*$", "", cand_cols))         # "LE PEN (FN)" -> "LE PEN"

  df <- raw[, c(dep_col, num_col, cand_cols)]
  names(df)[1:2] <- c(".dep", ".num")
  df[cand_cols] <- lapply(df[cand_cols], function(x) suppressWarnings(as.numeric(x)))
  votes <- df |>
    tidyr::pivot_longer(all_of(cand_cols), names_to = ".hdr", values_to = "voix") |>
    filter(!is.na(voix)) |>
    mutate(year = yr, round = rd,
           code_commune = make_commune_code(.dep, .num),
           code_departement = ifelse(grepl("^[0-9]+$", trimws(.dep)),
                                     formatC(as.integer(.dep), width = 2, flag = "0"), toupper(trimws(.dep))),
           nom = setNames(surname, cand_cols)[.hdr],
           nom_norm = norm_name(nom),
           prenom = NA_character_,
           coverage = "communes_gt_9000") |>
    select(year, round, code_departement, code_commune, nom, prenom, nom_norm, voix, coverage)

  # turnout for these communes (inscrits/votants/exprimes) for downstream shares
  turn <- raw |>
    transmute(year = yr, round = rd,
              code_commune = make_commune_code(.data[[dep_col]], .data[[num_col]]),
              inscrits = suppressWarnings(as.numeric(.data[[hdr[nh == "inscrits"][1]]])),
              votants  = suppressWarnings(as.numeric(.data[[hdr[nh == "votants"][1]]])),
              exprimes = suppressWarnings(as.numeric(.data[[hdr[nh == "exprimes"][1]]]))) |>
    filter(!is.na(exprimes))
  list(votes = votes, turnout = turn)
}

read_historical_commune <- function() {
  files <- list.files(file.path(PATHS$raw, "elections"),
                      pattern = "^cdsp_presi\\d{4}t\\d_commp9000\\.csv$", full.names = TRUE)
  if (length(files) == 0) {
    message("[note] No CDSP commune files for 1988/1995. Run download_historical_elections().")
    return(list(votes = tibble(), turnout = tibble()))
  }
  parsed <- lapply(files, parse_cdsp_commune)
  list(votes   = bind_rows(lapply(parsed, `[[`, "votes")),
       turnout = bind_rows(lapply(parsed, `[[`, "turnout")))
}

# --- Aggregate everything to commune level (all 7 years) -----------------
clean_votes_commune <- function() {
  bv <- arrow::read_parquet(file.path(PATHS$interim, "votes_bv.parquet"))
  bv_commune <- bv |>
    group_by(year, round, code_departement, code_commune, nom, prenom, nom_norm) |>
    summarise(voix = sum(voix, na.rm = TRUE), .groups = "drop") |>
    mutate(coverage = "full")

  hist <- read_historical_commune()
  if (nrow(hist$turnout) > 0)
    write_parquet(hist$turnout, file.path(PATHS$interim, "turnout_historical.parquet"))

  commune <- bind_rows(bv_commune, hist$votes) |>
    filter(year %in% ELECTION_YEARS)

  write_parquet(commune, file.path(PATHS$interim, "votes_commune.parquet"))
  message("votes_commune: ", nrow(commune), " rows, years ",
          paste(sort(unique(commune$year)), collapse = ","),
          "; historical commune rows: ", nrow(hist$votes))
  invisible(commune)
}

if (sys.nframe() == 0) {
  clean_votes_bv()
  clean_turnout_bv()
  clean_votes_commune()
}
