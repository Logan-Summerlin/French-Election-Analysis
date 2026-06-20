# 08_left_classification.R -----------------------------------------------
# Apply the editable lookup (data/lookups/left_classification.csv) to vote
# tables, then derive per-unit aggregates: total-Left share + per-family shares.
#
# Join key is (year, normalized surname) because the open dataset's `nuance`
# field is empty for 2017/2022. Editing the CSV (flip is_left, add rows, change
# family) re-derives every aggregate with no code change.

source(here::here("R", "config.R"))
suppressPackageStartupMessages({ library(dplyr); library(readr); library(stringr); library(stringi); library(tidyr) })

norm_name <- function(x) stri_trans_general(toupper(trimws(x)), "Latin-ASCII")

load_left_lookup <- function() {
  read_csv(file.path(PATHS$lookups, "left_classification.csv"), show_col_types = FALSE) |>
    mutate(nom_norm = norm_name(nom)) |>
    select(year, nom_norm, party, family, is_left)
}

# Attach party/family/is_left to a long candidate-vote table.
classify_votes <- function(votes, lookup = load_left_lookup()) {
  joined <- votes |>
    left_join(lookup, by = c("year", "nom_norm"))
  unmatched <- joined |> filter(is.na(is_left)) |> distinct(year, nom_norm)
  if (nrow(unmatched) > 0)
    warning("Unclassified candidates (add to left_classification.csv): ",
            paste(unmatched$year, unmatched$nom_norm, collapse = "; "))
  joined |> mutate(is_left = coalesce(is_left, 0L),
                   family = coalesce(family, "non_classe"))
}

# Per-unit aggregates. `unit_cols` identify the spatial unit (e.g. code_commune
# or bv_id). `denom` = exprimes (vote share denominator).
compute_left_aggregates <- function(classified, unit_cols, denom_col = "exprimes") {
  base <- classified |>
    group_by(across(all_of(c(unit_cols, "year", "round"))))

  total <- base |>
    summarise(left_votes = sum(voix[is_left == 1], na.rm = TRUE),
              all_votes  = sum(voix, na.rm = TRUE),
              .groups = "drop") |>
    mutate(total_left_share = 100 * left_votes / all_votes)

  by_family <- classified |>
    filter(is_left == 1) |>
    group_by(across(all_of(c(unit_cols, "year", "round"))), family) |>
    summarise(fam_votes = sum(voix, na.rm = TRUE), .groups = "drop") |>
    left_join(select(total, all_of(c(unit_cols, "year", "round")), all_votes),
              by = c(unit_cols, "year", "round")) |>
    mutate(fam_share = 100 * fam_votes / all_votes) |>
    select(all_of(c(unit_cols, "year", "round")), family, fam_share) |>
    pivot_wider(names_from = family, values_from = fam_share,
                names_glue = "left_{family}_share", values_fill = 0)

  total |> select(all_of(c(unit_cols, "year", "round")), total_left_share) |>
    left_join(by_family, by = c(unit_cols, "year", "round"))
}

if (sys.nframe() == 0) {
  lk <- load_left_lookup()
  message("lookup rows: ", nrow(lk), "; left candidates: ", sum(lk$is_left))
}
