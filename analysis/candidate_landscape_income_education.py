#!/usr/bin/env python3
"""Candidate-winner landscapes by income and higher education.

For the 2002 and 2022 French presidential first rounds, this script:

1. joins bureau-de-vote results to commune-level INSEE income and education;
2. evaluates a regular income/education grid;
3. finds the precincts nearest each grid point after standardising the two
   demographic axes; and
4. colours the grid either by the candidate with the highest mean first-round
   vote share or by that winning mean vote share.

Three figures are written per election: categorical complete-sample and central
90-percent-axis versions based on 100 nearest precincts, plus a central-90%
continuous winning-vote-share version based on 25 nearest precincts. To follow
the repository's established comparison, 2002 is paired with the earliest
Filosofi vintage (2012) and 2012 education, while 2022 is paired with 2021
Filosofi and census education.

The election result is precinct-level.  Income and education are commune-level
attributes attached to each precinct, so the figures are ecological summaries,
not estimates of individual voter behaviour.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, Normalize
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from PIL import Image
import pyarrow.parquet as pq
from scipy.ndimage import distance_transform_edt, label as connected_components
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = Path(os.environ.get("RAW_DIR", "/tmp/fr_candidate_landscape"))
DEFAULT_PROCESSED = ROOT / "data" / "processed"
DEFAULT_OUTPUT = ROOT / "outputs" / "candidate_landscapes"

ELECTION_BASE = "https://object.files.data.gouv.fr/data-pipeline-open/elections"
SOURCES = {
    "candidats_results.parquet": f"{ELECTION_BASE}/candidats_results.parquet",
    "general_results.parquet": f"{ELECTION_BASE}/general_results.parquet",
    "diplomes_2012.zip": (
        "https://www.insee.fr/fr/statistiques/fichier/2044707/"
        "base-cc-diplomes-formation_2012.zip"
    ),
    "filosofi_2012.zip": (
        "https://www.insee.fr/fr/statistiques/fichier/1895078/"
        "revenu-pauvrete-menage-2012.zip"
    ),
    "diplomes_2021.zip": (
        "https://www.insee.fr/fr/statistiques/fichier/8268840/"
        "base-ic-diplomes-formation-2021_csv.zip"
    ),
    "filosofi_2021.zip": (
        "https://www.insee.fr/fr/statistiques/fichier/7756729/"
        "base-cc-filosofi-2021-geo2023-histo_CSV.zip"
    ),
}

YEAR_CONFIG = {
    2002: {"census_vintage": 2012, "election_id": "2002_pres_t1"},
    2022: {"census_vintage": 2021, "election_id": "2022_pres_t1"},
}

# Familiar French political colours.  The legend only shows candidates that
# win at least one grid cell, so the 16-candidate 2002 contest remains readable.
CANDIDATE_COLOURS = {
    "ARTHAUD": "#9E0142",
    "BAYROU": "#F2C14E",
    "BESANCENOT": "#D73027",
    "BOUTIN": "#A67C52",
    "CHEVENEMENT": "#777777",
    "CHIRAC": "#4C78A8",
    "DUPONT-AIGNAN": "#6B8E23",
    "GLUCKSTEIN": "#7F0000",
    "HIDALGO": "#E76F93",
    "HUE": "#B30000",
    "JADOT": "#59A14F",
    "JOSPIN": "#E15759",
    "LAGUILLER": "#B2182B",
    "LASSALLE": "#9C755F",
    "LE PEN": "#244A8F",
    "LEPAGE": "#76B7B2",
    "MACRON": "#F4C95D",
    "MADELIN": "#6BAED6",
    "MAMERE": "#43A047",
    "MEGRET": "#273B70",
    "MÉLENCHON": "#D73027",
    "PÉCRESSE": "#3F72AF",
    "POUTOU": "#C51B7D",
    "ROUSSEL": "#B51E2E",
    "SAINT-JOSSE": "#8C6D31",
    "TAUBIRA": "#7B3294",
    "ZEMMOUR": "#6C4E7C",
}


def fetch_sources(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        destination = raw_dir / name
        if destination.exists() and destination.stat().st_size > 0:
            continue
        print(f"downloading {name} ...", flush=True)
        subprocess.run(
            [
                "curl",
                "-L",
                "-sS",
                "--retry",
                "4",
                "--retry-delay",
                "2",
                "--max-time",
                "900",
                "-o",
                str(destination),
                url,
            ],
            check=True,
        )


def extract_once(archive: Path, destination: Path) -> Path:
    marker = destination / ".complete"
    if not marker.exists():
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(destination)
        marker.touch()
    return destination


def first_file(directory: Path, predicate) -> Path:
    matches = sorted(path for path in directory.rglob("*") if path.is_file() and predicate(path))
    if not matches:
        raise FileNotFoundError(f"No matching file below {directory}")
    return matches[0]


def clean_code(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


def socioeconomic_2012(raw_dir: Path) -> pd.DataFrame:
    dip_dir = extract_once(raw_dir / "diplomes_2012.zip", raw_dir / "diplomes_2012")
    inc_dir = extract_once(raw_dir / "filosofi_2012.zip", raw_dir / "filosofi_2012")
    dip_file = first_file(dip_dir, lambda p: p.suffix.lower() == ".xls")
    inc_file = first_file(
        inc_dir, lambda p: p.suffix.lower() == ".xls" and "filosofi" in p.name.lower()
    )

    education = pd.read_excel(
        dip_file,
        sheet_name="COM_2012",
        header=5,
        usecols=["CODGEO", "P12_NSCOL15P", "P12_NSCOL15P_BACP2", "P12_NSCOL15P_SUP"],
        dtype={"CODGEO": str},
        engine="xlrd",
    )
    for column in ["P12_NSCOL15P", "P12_NSCOL15P_BACP2", "P12_NSCOL15P_SUP"]:
        education[column] = pd.to_numeric(education[column], errors="coerce")
    education["higher_ed_pct"] = 100 * (
        education["P12_NSCOL15P_BACP2"] + education["P12_NSCOL15P_SUP"]
    ) / education["P12_NSCOL15P"]

    income = pd.read_excel(
        inc_file,
        sheet_name="COM",
        header=5,
        usecols=["CODGEO", "MED12"],
        dtype={"CODGEO": str},
        engine="xlrd",
    )
    income["median_income"] = pd.to_numeric(income["MED12"], errors="coerce")

    education["code_commune"] = clean_code(education["CODGEO"])
    income["code_commune"] = clean_code(income["CODGEO"])
    return education[["code_commune", "higher_ed_pct"]].merge(
        income[["code_commune", "median_income"]], on="code_commune", how="inner"
    )


def socioeconomic_2021(raw_dir: Path) -> pd.DataFrame:
    dip_dir = extract_once(raw_dir / "diplomes_2021.zip", raw_dir / "diplomes_2021")
    inc_dir = extract_once(raw_dir / "filosofi_2021.zip", raw_dir / "filosofi_2021")
    dip_file = first_file(
        dip_dir,
        lambda p: p.suffix.lower() == ".csv"
        and "diplomes" in p.name.lower()
        and not p.name.lower().startswith("meta"),
    )
    inc_file = first_file(
        inc_dir,
        lambda p: p.suffix.lower() == ".csv"
        and "filosofi_2021_com" in p.name.lower()
        and not p.name.lower().startswith("meta"),
    )

    columns = [
        "COM",
        "P21_NSCOL15P",
        "P21_NSCOL15P_SUP2",
        "P21_NSCOL15P_SUP34",
        "P21_NSCOL15P_SUP5",
    ]
    education = pd.read_csv(dip_file, sep=";", usecols=columns, dtype={"COM": str})
    for column in columns[1:]:
        education[column] = pd.to_numeric(education[column], errors="coerce")
    education = education.groupby("COM", as_index=False)[columns[1:]].sum(min_count=1)
    education["higher_ed_pct"] = 100 * education[columns[2:]].sum(axis=1) / education[columns[1]]

    income = pd.read_csv(inc_file, sep=";", usecols=["CODGEO", "MED21"], dtype=str)
    income["median_income"] = pd.to_numeric(
        income["MED21"].str.replace(",", ".", regex=False), errors="coerce"
    )

    education["code_commune"] = clean_code(education["COM"])
    income["code_commune"] = clean_code(income["CODGEO"])
    return education[["code_commune", "higher_ed_pct"]].merge(
        income[["code_commune", "median_income"]], on="code_commune", how="inner"
    )


def metropolitan_mask(department: pd.Series) -> pd.Series:
    code = department.astype("string").str.upper().str.strip()
    return ~code.str.startswith(("97", "98", "99")) & code.ne("ZZ") & code.notna()


def election_precincts(raw_dir: Path, year: int, socio: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    election_id = YEAR_CONFIG[year]["election_id"]
    keys = ["code_departement", "code_commune", "code_bv"]

    general = pq.read_table(
        raw_dir / "general_results.parquet",
        columns=["id_election", *keys, "exprimes"],
        filters=[("id_election", "=", election_id)],
    ).to_pandas()
    general = general[metropolitan_mask(general["code_departement"]) & (general["exprimes"] >= 50)].copy()
    general["code_commune"] = clean_code(general["code_commune"])

    candidates = pq.read_table(
        raw_dir / "candidats_results.parquet",
        columns=["id_election", *keys, "nom", "voix"],
        filters=[("id_election", "=", election_id)],
    ).to_pandas()
    candidates = candidates[metropolitan_mask(candidates["code_departement"])].copy()
    candidates["code_commune"] = clean_code(candidates["code_commune"])
    candidates["nom"] = candidates["nom"].astype("string").str.strip().str.upper()
    candidates["voix"] = pd.to_numeric(candidates["voix"], errors="coerce")

    wide = candidates.pivot_table(
        index=keys,
        columns="nom",
        values="voix",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    candidate_names = sorted(column for column in wide.columns if column not in keys)
    data = (
        general.merge(wide, on=keys, how="inner", validate="one_to_one")
        .merge(socio, on="code_commune", how="inner", validate="many_to_one")
        .dropna(subset=["median_income", "higher_ed_pct"])
    )
    data = data[
        np.isfinite(data["median_income"])
        & np.isfinite(data["higher_ed_pct"])
        & data["median_income"].gt(0)
        & data["higher_ed_pct"].between(0, 100)
    ].copy()
    data[candidate_names] = (
        100 * data[candidate_names].fillna(0).div(data["exprimes"], axis=0)
    ).astype("float32")
    row_totals = data[candidate_names].sum(axis=1)
    if not row_totals.between(99.99, 100.01).all():
        raise ValueError(f"{year}: candidate vote shares do not sum to 100% for every precinct")
    return data, candidate_names


def candidate_colours(candidate_names: list[str]) -> list[str]:
    fallback = plt.get_cmap("tab20")
    return [
        CANDIDATE_COLOURS.get(candidate, matplotlib.colors.to_hex(fallback(i % 20)))
        for i, candidate in enumerate(candidate_names)
    ]


def winner_surface(
    data: pd.DataFrame,
    candidate_names: list[str],
    neighbours: int,
    nx: int,
    ny: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = data["median_income"].to_numpy(float)
    y = data["higher_ed_pct"].to_numpy(float)
    x_grid = np.linspace(x.min(), x.max(), nx)
    y_grid = np.linspace(y.min(), y.max(), ny)
    grid_x, grid_y = np.meshgrid(x_grid, y_grid)

    axes = np.column_stack([x, y])
    centre = axes.mean(axis=0)
    scale = axes.std(axis=0)
    scale[scale == 0] = 1
    tree = cKDTree((axes - centre) / scale)
    queries = (np.column_stack([grid_x.ravel(), grid_y.ravel()]) - centre) / scale
    shares = data[candidate_names].to_numpy(dtype="float32")
    k = min(neighbours, len(data))
    winners = np.empty(len(queries), dtype=np.int16)
    winning_shares = np.empty(len(queries), dtype=np.float32)

    chunk_size = 4_000
    for start in range(0, len(queries), chunk_size):
        stop = min(start + chunk_size, len(queries))
        try:
            neighbour_index = tree.query(queries[start:stop], k=k, workers=-1)[1]
        except TypeError:  # scipy < 1.6
            neighbour_index = tree.query(queries[start:stop], k=k)[1]
        if k == 1:
            neighbour_index = neighbour_index[:, None]
        mean_shares = shares[neighbour_index].mean(axis=1)
        winners[start:stop] = np.argmax(mean_shares, axis=1)
        winning_shares[start:stop] = np.max(mean_shares, axis=1)
    return winners.reshape(ny, nx), winning_shares.reshape(ny, nx), x_grid, y_grid


def readable_text_colour(hex_colour: str) -> str:
    red, green, blue = matplotlib.colors.to_rgb(hex_colour)
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#111111" if luminance > 0.56 else "#FFFFFF"


def label_regions(
    ax: plt.Axes,
    surface: np.ndarray,
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    candidate_names: list[str],
    colours: list[str],
    fixed_text_colour: str | None = None,
) -> list[plt.Text]:
    labels: list[plt.Text] = []
    total_cells = surface.size
    for index in np.unique(surface):
        mask = surface == index
        components, count = connected_components(mask)
        if count == 0:
            continue
        component_sizes = np.bincount(components.ravel())
        component_sizes[0] = 0
        largest = int(component_sizes.argmax())
        region = components == largest
        if region.sum() < 0.008 * total_cells:
            continue
        row, column = np.unravel_index(np.argmax(distance_transform_edt(region)), region.shape)
        text_colour = fixed_text_colour or readable_text_colour(colours[index])
        outline = "white" if text_colour == "#111111" else "black"
        # Keep even long names such as "Mélenchon" fully inside the axes.
        x_padding = 0.075 * (x_grid.max() - x_grid.min())
        y_padding = 0.050 * (y_grid.max() - y_grid.min())
        text_x = np.clip(x_grid[column], x_grid.min() + x_padding, x_grid.max() - x_padding)
        text_y = np.clip(y_grid[row], y_grid.min() + y_padding, y_grid.max() - y_padding)
        label = ax.text(
            text_x,
            text_y,
            candidate_names[index].title(),
            ha="center",
            va="center",
            color=text_colour,
            fontsize=12,
            fontweight="bold",
            zorder=4,
            clip_on=True,
        )
        label.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground=outline, alpha=0.7)])
        labels.append(label)
    return labels


def validate_layout(fig: plt.Figure, ax: plt.Axes, region_labels: list[plt.Text]) -> None:
    """Fail the build if text is clipped by the canvas or plot boundary."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    axes_box = ax.get_window_extent(renderer)

    checked_text = [*fig.texts]
    for figure_axis in fig.axes:
        checked_text.extend(
            [
                figure_axis.title,
                figure_axis.xaxis.label,
                figure_axis.yaxis.label,
                *figure_axis.get_xticklabels(),
                *figure_axis.get_yticklabels(),
            ]
        )
        legend = figure_axis.get_legend()
        if legend is not None:
            checked_text.extend(legend.get_texts())
            checked_text.append(legend.get_title())

    for artist in checked_text:
        if not artist.get_visible() or not artist.get_text().strip():
            continue
        box = artist.get_window_extent(renderer)
        # Locators can retain ticks just outside the displayed range. They are
        # not rendered, so exclude them from the canvas-clipping assertion.
        if any(
            artist in figure_axis.get_xticklabels()
            and not figure_axis.get_window_extent(renderer).overlaps(box)
            for figure_axis in fig.axes
        ):
            continue
        if any(
            artist in figure_axis.get_yticklabels()
            and not figure_axis.get_window_extent(renderer).overlaps(box)
            for figure_axis in fig.axes
        ):
            continue
        if box.x0 < -1 or box.y0 < -1 or box.x1 > canvas.x1 + 1 or box.y1 > canvas.y1 + 1:
            raise ValueError(f"Text falls outside figure canvas: {artist.get_text()!r}")

    for artist in region_labels:
        box = artist.get_window_extent(renderer)
        if (
            box.x0 < axes_box.x0 + 2
            or box.y0 < axes_box.y0 + 2
            or box.x1 > axes_box.x1 - 2
            or box.y1 > axes_box.y1 - 2
        ):
            raise ValueError(f"Candidate label is clipped by plot boundary: {artist.get_text()!r}")


def save_verified_png(fig: plt.Figure, output: Path, palette_colours: int | None = None) -> None:
    """Render in memory and refuse to retain a damaged PNG."""
    buffer = BytesIO()
    fig.savefig(
        buffer,
        format="png",
        dpi=150,
        facecolor="white",
        pil_kwargs={"optimize": True, "compress_level": 9},
    )
    contents = buffer.getvalue()
    with Image.open(BytesIO(contents)) as image:
        image.verify()
    if palette_colours is not None:
        with Image.open(BytesIO(contents)) as image:
            quantized = image.convert("RGB").quantize(
                colors=palette_colours,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
            compact = BytesIO()
            quantized.save(compact, format="PNG", optimize=True, compress_level=9)
        contents = compact.getvalue()
    output.write_bytes(contents)
    with Image.open(output) as image:
        image.verify()


def plot_landscape(
    data: pd.DataFrame,
    candidate_names: list[str],
    year: int,
    census_vintage: int,
    trimmed: bool,
    out_dir: Path,
    neighbours: int,
    grid_size: int,
    shade_by_winning_share: bool = False,
) -> dict[str, float | int | str]:
    original_n = len(data)
    if trimmed:
        income_low, income_high = data["median_income"].quantile([0.05, 0.95])
        education_low, education_high = data["higher_ed_pct"].quantile([0.05, 0.95])
        plotted = data[
            data["median_income"].between(income_low, income_high)
            & data["higher_ed_pct"].between(education_low, education_high)
        ].copy()
    else:
        plotted = data.copy()

    ny = max(180, int(grid_size * 0.68))
    surface, winning_shares, x_grid, y_grid = winner_surface(
        plotted, candidate_names, neighbours=neighbours, nx=grid_size, ny=ny
    )
    colours = candidate_colours(candidate_names)

    fig, ax = plt.subplots(figsize=(12, 8))
    image_extent = [x_grid.min(), x_grid.max(), y_grid.min(), y_grid.max()]
    if shade_by_winning_share:
        share_floor = 5 * np.floor(winning_shares.min() / 5)
        share_ceiling = 5 * np.ceil(winning_shares.max() / 5)
        share_norm = Normalize(vmin=share_floor, vmax=share_ceiling)
        image = ax.imshow(
            winning_shares,
            origin="lower",
            aspect="auto",
            interpolation="nearest",
            extent=image_extent,
            cmap="viridis",
            norm=share_norm,
            zorder=0,
        )
    else:
        image = ax.imshow(
            surface,
            origin="lower",
            aspect="auto",
            interpolation="nearest",
            extent=image_extent,
            cmap=ListedColormap(colours),
            vmin=-0.5,
            vmax=len(candidate_names) - 0.5,
            alpha=0.82,
            zorder=0,
        )
    ax.scatter(
        plotted["median_income"],
        plotted["higher_ed_pct"],
        s=3.2,
        color="#151515",
        alpha=0.10,
        linewidths=0,
        rasterized=True,
        zorder=2,
    )
    region_labels = label_regions(
        ax,
        surface,
        x_grid,
        y_grid,
        candidate_names,
        colours,
        fixed_text_colour="#FFFFFF" if shade_by_winning_share else None,
    )

    subtitle = "central 90% of each demographic axis" if trimmed else "complete matched sample"
    fig.text(
        0.10,
        0.965,
        f"France {year} presidential election — first round\n"
        + (
            "Local winning vote share by income and education"
            if shade_by_winning_share
            else "Leading candidate by local income and education"
        ),
        ha="left",
        va="top",
        fontsize=20,
        fontweight="bold",
        linespacing=1.08,
    )
    fig.text(
        0.10,
        0.855,
        f"{subtitle}; "
        + (f"{neighbours} nearest precincts; " if shade_by_winning_share else "")
        + f"income and education vintage: INSEE {census_vintage}",
        ha="left",
        va="top",
        fontsize=10.5,
        color="#4B4B4B",
    )
    ax.set_xlabel("Median disposable income (€ per consumption unit)", fontsize=12, fontweight="bold")
    ax.set_ylabel("College diploma or higher (% of non-schooled population 15+)", fontsize=12, fontweight="bold")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"€{value / 1000:.0f}k"))
    ax.grid(color="white", alpha=0.30, linewidth=0.7)
    ax.set_axisbelow(False)
    ax.tick_params(labelsize=10)

    winner_indices = sorted(np.unique(surface), key=lambda i: candidate_names[i])
    if shade_by_winning_share:
        colour_axis = fig.add_axes([0.835, 0.28, 0.022, 0.43])
        colour_bar = fig.colorbar(image, cax=colour_axis)
        colour_bar.set_label(
            "Mean vote share of local winner (%)",
            fontsize=10,
            fontweight="bold",
            labelpad=10,
        )
        colour_bar.ax.tick_params(labelsize=9)
    else:
        legend = [
            Patch(facecolor=colours[index], edgecolor="none", label=candidate_names[index].title())
            for index in winner_indices
        ]
        ax.legend(
            handles=legend,
            title="Surface winner",
            loc="upper left",
            bbox_to_anchor=(1.012, 1),
            borderaxespad=0,
            frameon=False,
            fontsize=10,
            title_fontsize=10,
        )

    retained = len(plotted) / original_n
    label_note = "; labels identify the local leader" if shade_by_winning_share else ""
    footnote_break = "\n" if shade_by_winning_share else " "
    fig.text(
        0.01,
        0.012,
        f"Each cell shows the highest mean vote share among the {neighbours} nearest precincts in "
        f"standardised income–education space.{footnote_break}"
        f"Dots are precincts{label_note}. "
        f"n={len(plotted):,} ({retained:.1%} of matched precincts).",
        ha="left",
        va="bottom",
        fontsize=8.6,
        color="#555555",
    )
    fig.subplots_adjust(left=0.10, right=0.81, top=0.79, bottom=0.13)
    validate_layout(fig, ax, region_labels)

    suffix = "central90" if trimmed else "full"
    if shade_by_winning_share:
        suffix += f"_k{neighbours}_winning_share"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"leading_candidate_income_education_{year}_{suffix}.png"
    save_verified_png(fig, output, palette_colours=256 if shade_by_winning_share else None)
    plt.close(fig)
    print(f"saved {output} ({len(plotted):,} precincts)")
    return {
        "year": year,
        "sample": suffix,
        "n": len(plotted),
        "matched_n": original_n,
        "income_min": float(plotted["median_income"].min()),
        "income_max": float(plotted["median_income"].max()),
        "education_min": float(plotted["higher_ed_pct"].min()),
        "education_max": float(plotted["higher_ed_pct"].max()),
        "neighbours": neighbours,
        "fill": "winning vote share" if shade_by_winning_share else "candidate",
        "winning_share_min": float(winning_shares.min()),
        "winning_share_max": float(winning_shares.max()),
        "surface_winners": ", ".join(candidate_names[index].title() for index in winner_indices),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--neighbours", type=int, default=100)
    parser.add_argument("--share-neighbours", type=int, default=25)
    parser.add_argument("--grid-size", type=int, default=320)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetch_sources(args.raw_dir)
    args.processed_dir.mkdir(parents=True, exist_ok=True)

    socioeconomic = {
        2002: socioeconomic_2012(args.raw_dir),
        2022: socioeconomic_2021(args.raw_dir),
    }
    summaries: list[dict[str, float | int | str]] = []
    for year in [2002, 2022]:
        data, candidates = election_precincts(args.raw_dir, year, socioeconomic[year])
        processed = args.processed_dir / f"candidate_landscape_{year}.parquet"
        data.to_parquet(processed, index=False)
        print(f"wrote {processed}: {len(data):,} matched precincts, {len(candidates)} candidates")
        for trimmed in [False, True]:
            summaries.append(
                plot_landscape(
                    data,
                    candidates,
                    year=year,
                    census_vintage=YEAR_CONFIG[year]["census_vintage"],
                    trimmed=trimmed,
                    out_dir=args.out_dir,
                    neighbours=args.neighbours,
                    grid_size=args.grid_size,
                )
            )
        summaries.append(
            plot_landscape(
                data,
                candidates,
                year=year,
                census_vintage=YEAR_CONFIG[year]["census_vintage"],
                trimmed=True,
                out_dir=args.out_dir,
                neighbours=args.share_neighbours,
                grid_size=args.grid_size,
                shade_by_winning_share=True,
            )
        )

    summary_path = args.out_dir / "build_summary.csv"
    pd.DataFrame(summaries).to_csv(summary_path, index=False)
    print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
