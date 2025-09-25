"""Shared helper utilities for MNE3SD scripts."""

from __future__ import annotations

import csv
import os
import statistics
import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

PROFILE_CHOICES = ("full", "ci")
PROFILE_ENV_VAR = "MNE3SD_PROFILE"
PROFILE_HELP = (
    "Execution profile preset. 'full' keeps the publication-grade defaults while "
    "'ci' minimises the workload for automated smoke tests. The preset can also be "
    f"supplied through the {PROFILE_ENV_VAR} environment variable."
)


def ensure_directory(path: str | Path) -> Path:
    """Ensure that ``path`` exists and return the created directory."""

    directory = Path(path)
    if directory.suffix and not directory.is_dir():
        directory = directory.parent
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def apply_ieee_style(figsize: tuple[float, float] = (3.5, 2.2)) -> None:
    """Apply a compact IEEE-friendly Matplotlib style."""

    plt.rcdefaults()
    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 7,
            "figure.figsize": figsize,
        }
    )


def save_figure(
    fig: "plt.Figure",
    basename: str | Path,
    output_dir: str | Path,
    *,
    dpi: int = 300,
) -> tuple[Path, Path]:
    """Save ``fig`` as PNG and EPS files inside ``output_dir``."""

    output_base = ensure_directory(output_dir) / Path(basename)
    png_path = output_base.with_suffix(".png")
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    eps_path = output_base.with_suffix(".eps")
    fig.savefig(eps_path, dpi=dpi, format="eps", bbox_inches="tight")
    return png_path, eps_path


def write_csv(
    path: str | Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]] | Iterable[dict[str, Any]],
) -> Path:
    """Write ``rows`` to ``path`` using the provided ``fieldnames``."""

    file_path = Path(path)
    ensure_directory(file_path.parent)
    with file_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return file_path


def summarise_metrics(
    data: Iterable[Mapping[str, Any]],
    group_keys: Sequence[str],
    value_keys: Sequence[str],
) -> list[dict[str, Any]]:
    """Return mean and population standard deviation for ``value_keys``."""

    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for entry in data:
        key = tuple(entry.get(group_key) for group_key in group_keys)
        grouped[key].append(entry)

    summaries: list[dict[str, Any]] = []
    for key, entries in grouped.items():
        summary = {group_key: value for group_key, value in zip(group_keys, key)}
        for value_key in value_keys:
            values: list[float] = []
            for entry in entries:
                value = entry.get(value_key)
                if isinstance(value, (int, float)):
                    values.append(float(value))
                elif isinstance(value, str):
                    stripped = value.strip()
                    if stripped:
                        try:
                            values.append(float(stripped))
                        except ValueError:
                            continue
            if values:
                summary[f"{value_key}_mean"] = statistics.fmean(values)
                summary[f"{value_key}_std"] = (
                    statistics.pstdev(values) if len(values) > 1 else 0.0
                )
            else:
                summary[f"{value_key}_mean"] = ""
                summary[f"{value_key}_std"] = ""
        summaries.append(summary)
    return summaries


def add_execution_profile_argument(parser) -> None:
    """Attach a shared ``--profile`` option to ``parser``."""

    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default=None,
        help=PROFILE_HELP,
    )


def resolve_execution_profile(
    selected: str | None, *, env_var: str = PROFILE_ENV_VAR
) -> str:
    """Return the execution profile resolved from CLI and environment input."""

    candidate = selected or os.getenv(env_var)
    if not candidate:
        return "full"
    profile = candidate.strip().lower()
    if profile in PROFILE_CHOICES:
        return profile
    warnings.warn(
        f"Unknown execution profile '{candidate}', falling back to 'full'.",
        RuntimeWarning,
        stacklevel=2,
    )
    return "full"

