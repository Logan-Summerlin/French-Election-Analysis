#!/usr/bin/env python3
"""
Build the precinct-level 2022 analysis dataset used by
scatter_left_vs_socioeconomic_2022.py.

This is a self-contained Python reproduction of the relevant slice of the R
pipeline (Tier B, 2022 round 1) using a *commune-level* census join instead of
the full dasymetric interpolation. It downloads the open sources directly and
writes data/processed/bv_2022_analysis.parquet.

Sources (all open):
  - Election results (Ministry of Interior via data.gouv object storage):
      general_results.parquet   (turnout/exprimés per bureau de vote)
      candidats_results.parquet (votes per candidate per bureau de vote)
  - INSEE 2021 census (IRIS): activité (CSP), diplômes (education)
  - INSEE 2021 Filosofi (commune): median disposable income (niveau de vie)
  - france-geojson commune polygons -> area -> population density

Left 2022 (from data/lookups/left_classification.csv, is_left == 1):
  Mélenchon, Jadot, Roussel, Hidalgo, Poutou, Arthaud.

Run:  python3 analysis/build_bv_2022_dataset.py
Env:  RAW_DIR (default /tmp/fr2022)  to cache downloads.
"""
import os
import sys
import subprocess
import zipfile
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get("RAW_DIR", "/tmp/fr2022")
os.makedirs(RAW, exist_ok=True)
OUT = os.path.join(ROOT, "data", "processed")
os.makedirs(OUT, exist_ok=True)

OBJ = "https://object.files.data.gouv.fr/data-pipeline-open/elections"
INSEE = "https://www.insee.fr/fr/statistiques/fichier"
SOURCES = {
    "general_results.parquet":  f"{OBJ}/general_results.parquet",
    "candidats_results.parquet": f"{OBJ}/candidats_results.parquet",
    "activite_2021.zip":  f"{INSEE}/8268843/base-ic-activite-residents-2021_csv.zip",
    "diplomes_2021.zip":  f"{INSEE}/8268840/base-ic-diplomes-formation-2021_csv.zip",
    "filo_com_2021.zip":  f"{INSEE}/7756729/base-cc-filosofi-2021-geo2023-histo_CSV.zip",
    "communes.geojson":   "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/communes.geojson",
}


def fetch(name, url):
    dest = os.path.join(RAW, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    print("downloading", name, "...", flush=True)
    subprocess.run(["curl", "-sS", "-o", dest, "--retry", "4", "--retry-delay", "2",
                    "--max-time", "600", url], check=True)
    return dest


def unzip(name):
    d = os.path.join(RAW, name.replace(".zip", ""))
    if not os.path.isdir(d):
        with zipfile.ZipFile(os.path.join(RAW, name)) as z:
            z.extractall(d)
    return d


def find(d, needle):
    for f in os.listdir(d):
        if needle.lower() in f.lower() and f.lower().endswith((".csv",)) and not f.lower().startswith("meta"):
            return os.path.join(d, f)
    raise FileNotFoundError(needle)


def is_metro(dep):
    s = dep.astype(str).str.upper().str.strip()
    return ~s.str.startswith(("97", "98", "99")) & (s.str.len() <= 3) & (s != "ZZ")


def main():
    for n, u in SOURCES.items():
        fetch(n, u)

    # --- election: precinct-level Left share, 2022 pres round 1 ---
    LEFT = {"MÉLENCHON", "JADOT", "ROUSSEL", "HIDALGO", "POUTOU", "ARTHAUD"}
    import pyarrow.parquet as pq
    c = pq.read_table(os.path.join(RAW, "candidats_results.parquet"),
                      columns=["id_election", "code_commune", "code_bv", "nom", "voix"]).to_pandas()
    c = c[c.id_election == "2022_pres_t1"]
    c["bv_id"] = c.code_commune.astype(str) + "_" + c.code_bv.astype(str)
    left = (c[c.nom.isin(LEFT)].groupby("bv_id")["voix"].sum().rename("left_voix").reset_index())

    g = pq.read_table(os.path.join(RAW, "general_results.parquet"),
                      columns=["id_election", "code_departement", "code_commune", "code_bv",
                               "inscrits", "exprimes", "votants", "abstentions"]).to_pandas()
    g = g[g.id_election == "2022_pres_t1"].copy()
    g["bv_id"] = g.code_commune.astype(str) + "_" + g.code_bv.astype(str)
    bv = g.merge(left, on="bv_id", how="left")
    bv["left_voix"] = bv.left_voix.fillna(0)
    bv = bv[is_metro(bv.code_departement) & (bv.exprimes > 0)].copy()
    bv["left_share"] = 100 * bv.left_voix / bv.exprimes
    bv["abstention_rate"] = 100 * bv.abstentions / bv.inscrits

    # --- census: commune-level 2021 ---
    enc = "latin-1"
    act_d, dip_d, filo_d = unzip("activite_2021.zip"), unzip("diplomes_2021.zip"), unzip("filo_com_2021.zip")

    act = pd.read_csv(find(act_d, "activite"), sep=";", dtype={"COM": str, "IRIS": str}, encoding=enc,
                      usecols=["IRIS", "COM"] + [f"C21_ACTOCC1564_CS{i}" for i in range(1, 7)] + ["P21_POP1564"])
    for i in range(1, 7):
        act[f"cs{i}"] = pd.to_numeric(act[f"C21_ACTOCC1564_CS{i}"], errors="coerce")
    csp = act.groupby("COM")[[f"cs{i}" for i in range(1, 7)]].sum()
    csp["actocc"] = csp.sum(axis=1)
    lab = {1: "csp_agri_pct", 2: "csp_indep_pct", 3: "csp_cadres_pct",
           4: "csp_interm_pct", 5: "csp_employes_pct", 6: "csp_ouvriers_pct"}
    for i, v in lab.items():
        csp[v] = 100 * csp[f"cs{i}"] / csp["actocc"]
    csp = csp[list(lab.values())].reset_index().rename(columns={"COM": "code_commune"})

    age = ["P21_POP0205", "P21_POP0610", "P21_POP1114", "P21_POP1517", "P21_POP1824", "P21_POP2529", "P21_POP30P"]
    dcol = ["P21_NSCOL15P", "P21_NSCOL15P_DIPLMIN", "P21_NSCOL15P_SUP2", "P21_NSCOL15P_SUP34", "P21_NSCOL15P_SUP5"]
    dip = pd.read_csv(find(dip_d, "diplomes"), sep=";", dtype={"COM": str}, encoding=enc, usecols=["COM"] + age + dcol)
    for col in age + dcol:
        dip[col] = pd.to_numeric(dip[col], errors="coerce")
    edu = dip.groupby("COM")[age + dcol].sum()
    edu["pop_tot"] = edu[age].sum(axis=1)
    edu["higher_ed_pct"] = 100 * (edu.P21_NSCOL15P_SUP2 + edu.P21_NSCOL15P_SUP34 + edu.P21_NSCOL15P_SUP5) / edu.P21_NSCOL15P
    edu["no_diploma_pct"] = 100 * edu.P21_NSCOL15P_DIPLMIN / edu.P21_NSCOL15P
    edu = edu[["pop_tot", "higher_ed_pct", "no_diploma_pct"]].reset_index().rename(columns={"COM": "code_commune"})

    inc = pd.read_csv(find(filo_d, "filosofi_2021_COM"), sep=";", dtype={"CODGEO": str}, encoding=enc, usecols=["CODGEO", "MED21"])
    inc["median_income"] = pd.to_numeric(inc.MED21.astype(str).str.replace(",", "."), errors="coerce")
    inc = inc.rename(columns={"CODGEO": "code_commune"})[["code_commune", "median_income"]]

    import geopandas as gpd
    geo = gpd.read_file(os.path.join(RAW, "communes.geojson"))
    codecol = [c for c in geo.columns if c.lower() in ("code", "insee", "id")][0]
    geo = geo.to_crs(2154)
    area = pd.DataFrame({"code_commune": geo[codecol].astype(str), "area_km2": geo.geometry.area / 1e6})

    cen = (csp.merge(edu, on="code_commune", how="outer")
              .merge(inc, on="code_commune", how="left")
              .merge(area, on="code_commune", how="left"))
    cen["pop_density"] = cen.pop_tot / cen.area_km2

    out = bv.merge(cen, on="code_commune", how="left")
    out = out[out.exprimes >= 50].copy()
    dest = os.path.join(OUT, "bv_2022_analysis.parquet")
    out.to_parquet(dest)
    wm = np.average(out.left_share, weights=out.exprimes)
    print(f"wrote {dest}: {len(out):,} precincts, weighted Left share {wm:.2f}%")


if __name__ == "__main__":
    sys.exit(main())
