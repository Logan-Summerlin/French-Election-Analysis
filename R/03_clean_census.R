# 03_clean_census.R ------------------------------------------------------
# Parse INSEE census + Filosofi files into tidy socioeconomic tables.
# Produces, per vintage:
#   data/interim/census_commune_<vintage>.parquet
#   data/interim/census_iris_<vintage>.parquet      (Tier B only; vintages >= 2012)
#
# INSEE column prefixes change by millesime (P12_, P17_, C17_, ...), so columns
# are detected by REGEX on their suffix rather than hard-coded names. Adjust the
# patterns below if INSEE renames a series.
#
# Socioeconomic blocks built here (all expressed as shares of the relevant base):
#   CSP (8 catEgories socioprofessionnelles), education, population, income.

source(here::here("R", "config.R"))
suppressPackageStartupMessages({
  library(dplyr); library(readr); library(stringr); library(arrow); library(tidyr)
})

CENSUS_DIR <- file.path(PATHS$raw, "census")

# Map INSEE CS code -> our column name. CS1..CS8 are stable across millesimes.
CSP_LABELS <- c(CS1 = "csp_agri_pct", CS2 = "csp_indep_pct", CS3 = "csp_cadres_pct",
                CS4 = "csp_interm_pct", CS5 = "csp_employes_pct", CS6 = "csp_ouvriers_pct",
                CS7 = "csp_retraites_pct", CS8 = "csp_autres_pct")

# Pick the first column whose name matches `pattern`; NA column if none.
pick <- function(df, pattern) {
  hit <- str_subset(names(df), pattern)
  if (length(hit) == 0) return(NULL)
  hit[1]
}

# --- CSP shares from an activity/population census table ------------------
# Expects population-15+-by-CS columns ending in _CS1.._CS8 (e.g. P17_POP15P_CS3).
build_csp <- function(df, id_col) {
  cs_cols <- setNames(
    lapply(names(CSP_LABELS), function(cs) pick(df, str_c("POP15P_", cs, "$"))),
    names(CSP_LABELS))
  present <- cs_cols[!vapply(cs_cols, is.null, logical(1))]
  if (length(present) == 0) { warning("No CSP columns found"); return(NULL) }
  out <- df |> transmute(id = .data[[id_col]])
  base <- rowSums(sapply(present, function(c) suppressWarnings(as.numeric(df[[c]]))), na.rm = TRUE)
  for (cs in names(present)) {
    out[[CSP_LABELS[[cs]]]] <- 100 * suppressWarnings(as.numeric(df[[present[[cs]]]])) / base
  }
  out$pop_15plus <- base
  out
}

# --- Education shares ----------------------------------------------------
# Higher-ed = diploma of higher education; no-diploma = "aucun / inferieur".
build_education <- function(df, id_col) {
  base   <- pick(df, "NSCOL15P$")
  sup    <- pick(df, "NSCOL15P_SUP")             # all higher-ed series summed below
  none   <- pick(df, "(NSCOL15P_DIPLMIN|NSCOL15P_SANS|NSCOL15P_DIPL0)")
  if (is.null(base)) { warning("No education base column"); return(NULL) }
  sup_cols <- str_subset(names(df), "NSCOL15P_SUP")
  b   <- suppressWarnings(as.numeric(df[[base]]))
  hi  <- if (length(sup_cols)) rowSums(sapply(sup_cols, function(c) suppressWarnings(as.numeric(df[[c]]))), na.rm = TRUE) else NA
  tibble(id = df[[id_col]],
         higher_ed_pct = 100 * hi / b,
         no_diploma_pct = if (!is.null(none)) 100 * suppressWarnings(as.numeric(df[[none]])) / b else NA_real_)
}

# --- Income (Filosofi): median standard of living -----------------------
build_income <- function(df, id_col) {
  med <- pick(df, "(DEC_MED|MED_DISP|MED$|Q2)")
  if (is.null(med)) { warning("No median-income column"); return(NULL) }
  tibble(id = df[[id_col]], median_income = suppressWarnings(as.numeric(df[[med]])))
}

# --- Driver: build one vintage at a given geography ----------------------
# geo = "commune" (id = code commune, 5 chars) or "iris" (id = code IRIS, 9 chars).
build_census_vintage <- function(vintage, geo = c("commune", "iris")) {
  geo <- match.arg(geo)
  find <- function(pat) {
    f <- list.files(CENSUS_DIR, pattern = pat, full.names = TRUE, ignore.case = TRUE)
    if (length(f)) f[1] else NA_character_
  }
  act  <- find(str_c("activite.*", vintage))      # CSP
  dip  <- find(str_c("diplomes.*", vintage))      # education
  pop  <- find(str_c("(struct-pop|population).*", vintage))
  filo <- find(str_c("FILO.*", vintage))          # income

  id_col_guess <- if (geo == "iris") "IRIS" else "CODGEO"
  rd <- function(f) if (is.na(f)) NULL else
    readr::read_delim(f, delim = ";", show_col_types = FALSE, guess_max = 1e5)

  parts <- list()
  if (!is.null(d <- rd(act)))  parts$csp <- build_csp(d, pick(d, "^(IRIS|CODGEO|COM)$") %||% id_col_guess)
  if (!is.null(d <- rd(dip)))  parts$edu <- build_education(d, pick(d, "^(IRIS|CODGEO|COM)$") %||% id_col_guess)
  if (!is.null(d <- rd(filo))) parts$inc <- build_income(d, pick(d, "^(IRIS|CODGEO|COM|DCIRIS)$") %||% id_col_guess)

  parts <- Filter(Negate(is.null), parts)
  if (length(parts) == 0) {
    message("[note] No census files for vintage ", vintage, " (geo=", geo,
            "). Place files in ", CENSUS_DIR, "; see R/01_download.R.")
    return(invisible(NULL))
  }
  out <- Reduce(function(a, b) full_join(a, b, by = "id"), parts) |>
    rename(geo_id = id) |> mutate(census_vintage = vintage, geo_level = geo)

  outfile <- file.path(PATHS$interim, str_glue("census_{geo}_{vintage}.parquet"))
  write_parquet(out, outfile)
  message("census ", geo, " ", vintage, ": ", nrow(out), " units -> ", basename(outfile))
  invisible(out)
}

`%||%` <- function(a, b) if (is.null(a) || is.na(a) || length(a) == 0) b else a

if (sys.nframe() == 0) {
  vmap <- read_csv(file.path(PATHS$lookups, "census_vintage_map.csv"), show_col_types = FALSE)
  for (v in unique(vmap$census_vintage)) build_census_vintage(v, "commune")
  for (v in intersect(unique(vmap$census_vintage), c(2012, 2017, 2021))) build_census_vintage(v, "iris")
}
