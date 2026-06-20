# 04_harmonize_communes.R ------------------------------------------------
# Harmonize commune codes across 1988-2022 to a single reference geography
# (GEO_REF_YEAR) using the INSEE COG "communes nouvelles" passage table.
#
# Over 34 years many communes merged (a few split / renumbered). We build a
# crosswalk old_code -> ref_code and expose remap_commune() used by Tier A.
# Merges: many old codes -> one ref code (aggregate votes by sum; census shares
# by population-weighted mean). Splits are rare and left 1:1 (documented limit).

source(here::here("R", "config.R"))
suppressPackageStartupMessages({ library(dplyr); library(readr); library(stringr) })

# Build (or load) the crosswalk to GEO_REF_YEAR.
load_cog_crosswalk <- function() {
  f <- list.files(file.path(PATHS$raw, "census"),
                  pattern = "passage.*commune|communes-nouvelles|table-passage",
                  full.names = TRUE, ignore.case = TRUE)
  if (length(f) == 0) {
    message("[note] No COG passage table found; using identity crosswalk. ",
            "Download from ", URLS$cog_landing, " to data/raw/census/.")
    return(NULL)
  }
  raw <- read_delim(f[1], delim = ";", show_col_types = FALSE)
  # Column names vary by release; detect 'before' and 'after' code columns.
  before <- str_subset(names(raw), regex("AVANT|CODE_ANC|COM_AV|^CODGEO$", ignore_case = TRUE))[1]
  after  <- str_subset(names(raw), regex("APRES|CODE_NOUV|COM_AP|COMPARENT", ignore_case = TRUE))[1]
  raw |>
    transmute(code_old = str_pad(.data[[before]], 5, pad = "0"),
              code_ref = str_pad(.data[[after]], 5, pad = "0")) |>
    distinct()
}

# Remap a commune-keyed table to the reference geography.
# `value_cols` summed (counts) ; `weight_col` used for weighting share_cols means.
remap_commune <- function(df, code_col = "code_commune",
                          xwalk = load_cog_crosswalk(),
                          value_cols = character(0),
                          share_cols = character(0),
                          weight_col = NULL,
                          group_extra = character(0)) {
  df <- df |> mutate(.code = str_pad(.data[[code_col]], 5, pad = "0"))
  if (!is.null(xwalk)) {
    df <- df |> left_join(xwalk, by = c(".code" = "code_old")) |>
      mutate(code_ref = coalesce(code_ref, .code))
  } else {
    df <- df |> mutate(code_ref = .code)
  }
  grp <- c("code_ref", group_extra)
  agg <- df |> group_by(across(all_of(grp)))
  out <- agg |> summarise(
    across(all_of(value_cols), ~ sum(.x, na.rm = TRUE)),
    across(all_of(share_cols),
           ~ if (!is.null(weight_col)) weighted.mean(.x, .data[[weight_col]], na.rm = TRUE)
             else mean(.x, na.rm = TRUE)),
    .groups = "drop") |>
    rename(!!code_col := code_ref) |>
    mutate(geo_ref_year = GEO_REF_YEAR)
  out
}

if (sys.nframe() == 0) {
  xw <- load_cog_crosswalk()
  message("COG crosswalk rows: ", if (is.null(xw)) 0 else nrow(xw))
}
