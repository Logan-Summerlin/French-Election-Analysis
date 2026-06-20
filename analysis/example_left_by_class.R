# example_left_by_class.R ------------------------------------------------
# Demonstration analysis: how the French Left vote relates to socioeconomic
# class, density, income, and education across the 7 elections.
# Run after the pipeline has produced outputs/tierA_commune_wide.parquet.

source(here::here("R", "config.R"))
suppressPackageStartupMessages({ library(dplyr); library(arrow); library(tidyr) })
# library(ggplot2); library(broom)   # uncomment for plots / tidy model output

panel <- arrow::read_parquet(file.path(PATHS$outputs, "tierA_commune_wide.parquet")) |>
  filter(round == 1)   # first round = coalition composition is meaningful

# --- 1. Total-Left share over time, weighted by registered voters ---------
trend <- panel |>
  group_by(year) |>
  summarise(left_share = weighted.mean(total_left_share, inscrits, na.rm = TRUE),
            .groups = "drop")
print(trend)

# --- 2. Left vs population density (urban-rural gradient) ------------------
density_grad <- panel |>
  mutate(density_q = ntile(pop_density, 5)) |>
  group_by(year, density_q) |>
  summarise(left = weighted.mean(total_left_share, inscrits, na.rm = TRUE), .groups = "drop") |>
  pivot_wider(names_from = density_q, values_from = left, names_prefix = "dens_q")
print(density_grad)

# --- 3. Cross-sectional regression per election ---------------------------
# Left share ~ class + density + income + education (commune-weighted OLS).
for (y in sort(unique(panel$year))) {
  d <- filter(panel, year == y)
  preds <- intersect(c("csp_ouvriers_pct","csp_cadres_pct","csp_employes_pct",
                       "higher_ed_pct","median_income"), names(d))
  d$log_density <- log1p(d$pop_density)
  fml <- reformulate(c("log_density", preds), "total_left_share")
  ok <- complete.cases(d[all.vars(fml)])
  if (sum(ok) < 50) next
  m <- lm(fml, data = d[ok, ], weights = d$inscrits[ok])
  cat("\n=== ", y, " (n=", sum(ok), ") ===\n", sep = ""); print(round(coef(m), 3))
}

# --- 4. Coalition recomposition: family shares over time ------------------
fam_cols <- grep("^left_.*_share$", names(panel), value = TRUE)
coalition <- panel |>
  group_by(year) |>
  summarise(across(all_of(fam_cols), ~ weighted.mean(.x, inscrits, na.rm = TRUE)),
            .groups = "drop")
print(coalition)

# Smoke-test expectation (2022): Left strongest in dense, lower-income,
# higher-education-mixed urban communes (Melenchon/LFI signature).
