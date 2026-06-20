# 05_crosswalk_bv.R ------------------------------------------------------
# Disaggregate census attributes onto bureau-de-vote polygons via
# POPULATION-WEIGHTED dasymetric interpolation, using the INSEE Filosofi 200m
# grid as the weight layer (where people actually live).
#
# Method (one pass, fully spatial):
#   1. Grid cells carry {population, median_income} (Filosofi 200m).
#   2. Tag each grid cell with the IRIS it falls in -> cell inherits IRIS shares
#      (CSP, education).
#   3. Tag each grid cell with the bureau de vote polygon it falls in.
#   4. Per bureau de vote: population-weighted mean of shares & income, summed
#      population, density = pop / polygon area.
#
# Output: data/processed/bv_census.parquet  (one row per bv_id; vintage = latest)
# Caveat: contours are a single ~2022 vintage; applying to earlier years assumes
# roughly stable boundaries (documented in docs/caveats.md).

source(here::here("R", "config.R"))
suppressPackageStartupMessages({
  library(sf); library(dplyr); library(stringr); library(arrow); library(readr)
})

crosswalk_bv_census <- function(grid_vintage = 2021, iris_vintage = 2021) {
  contours_path <- file.path(PATHS$raw, "contours", "contours-france-entiere-latest-v2.geojson")
  grid_path <- list.files(file.path(PATHS$raw, "census"),
                          pattern = str_c("Filosofi.*", grid_vintage, ".*(gpkg|shp)$"),
                          full.names = TRUE, ignore.case = TRUE)
  iris_geo  <- list.files(file.path(PATHS$raw, "census"),
                          pattern = "iris.*(gpkg|shp)$", full.names = TRUE, ignore.case = TRUE)
  if (!file.exists(contours_path) || length(grid_path) == 0) {
    message("[note] Need bv contours + Filosofi grid for Tier B interpolation. ",
            "See R/01_download.R. Skipping crosswalk_bv_census().")
    return(invisible(NULL))
  }

  bv   <- st_read(contours_path, quiet = TRUE) |> st_transform(CRS_LAMBERT93)
  # contours file keys bv by 'id_bv' / 'code'; normalize to bv_id = commune_codebv
  bv <- bv |> mutate(bv_id = coalesce(.data[["id_bv"]], .data[["code"]], .data[["id"]]),
                     bv_area_km2 = as.numeric(st_area(geometry)) / 1e6) |>
    select(bv_id, bv_area_km2)

  grid <- st_read(grid_path[1], quiet = TRUE) |> st_transform(CRS_LAMBERT93)
  # Filosofi grid columns: Ind (population), Ind_snv / median income proxy.
  gpop <- str_subset(names(grid), regex("^Ind$|^ind$|Men_pop|pop", ignore_case = TRUE))[1]
  ginc <- str_subset(names(grid), regex("snv|med|disp|revenu", ignore_case = TRUE))[1]
  grid <- grid |> mutate(cell_pop = as.numeric(.data[[gpop]]),
                         cell_income = if (!is.na(ginc)) as.numeric(.data[[ginc]]) else NA_real_) |>
    st_centroid()

  # 1. cell -> IRIS shares (CSP, education)
  if (length(iris_geo)) {
    iris <- st_read(iris_geo[1], quiet = TRUE) |> st_transform(CRS_LAMBERT93)
    iris_attr <- arrow::read_parquet(file.path(PATHS$interim, str_glue("census_iris_{iris_vintage}.parquet")))
    iris <- iris |> mutate(geo_id = .data[[str_subset(names(iris), "IRIS|CODE_IRIS")[1]]]) |>
      left_join(iris_attr, by = "geo_id")
    grid <- st_join(grid, iris, join = st_within)
  }

  # 2. cell -> bureau de vote
  grid <- st_join(grid, bv, join = st_within) |> st_drop_geometry() |> filter(!is.na(bv_id))

  share_cols <- intersect(
    c("csp_agri_pct","csp_indep_pct","csp_cadres_pct","csp_interm_pct",
      "csp_employes_pct","csp_ouvriers_pct","csp_retraites_pct","csp_autres_pct",
      "higher_ed_pct","no_diploma_pct"), names(grid))

  pwm <- function(x, w) stats::weighted.mean(x, w, na.rm = TRUE)
  bv_census <- grid |>
    group_by(bv_id) |>
    summarise(
      pop = sum(cell_pop, na.rm = TRUE),
      median_income = pwm(cell_income, cell_pop),
      across(all_of(share_cols), ~ pwm(.x, cell_pop)),
      .groups = "drop") |>
    left_join(st_drop_geometry(bv), by = "bv_id") |>
    mutate(pop_density = pop / bv_area_km2,
           census_vintage = iris_vintage,
           interp_quality_flag = if_else(pop > 0 & !is.na(median_income), "ok", "sparse"))

  outfile <- file.path(PATHS$processed, "bv_census.parquet")
  write_parquet(bv_census, outfile)
  message("bv_census: ", nrow(bv_census), " bureaux de vote -> ", basename(outfile))
  invisible(bv_census)
}

if (sys.nframe() == 0) crosswalk_bv_census()
