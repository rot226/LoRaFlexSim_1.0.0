#!/usr/bin/env python3
"""Plot metrics from an aggregated mobility multichannel simulation.

Usage::

    python scripts/plot_mobility_multichannel.py results/mobility_multichannel.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot(
    csv_path: str,
    output_dir: str = "figures",
    max_delay: float | None = None,
    max_energy: float | None = None,
) -> None:
    df = pd.read_csv(csv_path)
    if hasattr(plt, "rcParams"):
        plt.rcParams.update({"font.size": 16})

    if "scenario" not in df.columns:
        raise ValueError("CSV must contain a 'scenario' column")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df["scenario_label"] = (
        "N="
        + df["nodes"].astype(int).astype(str)
        + ", C="
        + df["channels"].astype(int).astype(str)
    )
    if "area_size" in df.columns:
        df["area"] = df["area_size"] ** 2
    optional_params = [
        ("interval", "interval={:g}s"),
        ("speed", "speed={:g}m/s"),
        ("area", "area={:g}m²"),
    ]
    for col, fmt in optional_params:
        if col in df.columns and df[col].nunique() > 1:
            df["scenario_label"] += ", " + df[col].map(lambda x: fmt.format(x))

    metrics = [
        ("pdr", "PDR", "%", "%.1f%%", "C0"),
        ("avg_delay_s", "Average delay", "s", "%.2f s", "C2"),
        ("energy_per_node", "Average energy per node", "J", "%.2f J", "C3"),
        ("avg_sf", "Average SF", "", "%.1f", "C4"),
    ]

    for metric, name, unit, fmt, color in metrics:
        mean_col = f"{metric}_mean"
        std_col = f"{metric}_std"
        if mean_col not in df.columns:
            continue
        yerr = df[std_col] if std_col in df.columns else None
        fig_width = max(16, 0.6 * len(df))
        fig, ax = plt.subplots(figsize=(fig_width, 8))
        label = f"{name} ({unit})"
        bars = ax.bar(
            range(len(df)),
            df[mean_col],
            yerr=yerr,
            capsize=4,
            color=color,
            label=label,
        )
        ax.set_xlabel("")
        ax.set_xticks(range(len(df)))
        ax.set_xticklabels(
            df["scenario_label"], rotation=45, ha="right"
        )
        ax.set_ylabel(label)
        if hasattr(ax, "tick_params"):
            ax.tick_params(axis="both", labelsize=16)

        if metric == "pdr":
            cap = 100.0
            ax.set_ylim(0, cap)
            ax.axhline(cap, linestyle="--", color="grey", label="100 %")
        elif metric == "avg_delay_s":
            cap = max_delay or df[mean_col].max() * 1.1
            ax.set_ylim(0, cap)
        elif metric == "energy_per_node":
            cap = max_energy or df[mean_col].max() * 1.1
            ax.set_ylim(0, cap)
        else:
            cap = df[mean_col].max() * 1.1
            ax.set_ylim(0, cap)

        title = f"{name} by scenario (0 ≤ {name} ≤ {cap:g} {unit})"
        ax.set_title(title)
        ax.bar_label(bars, fmt=fmt, label_type="center")
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, 1.25),
            ncol=1,
            title="N: nombre de nœuds, C: nombre de canaux, speed: m/s",
        )
        fig.tight_layout(rect=[0, 0, 1, 0.9])
        for ext in ("png", "jpg", "eps", "svg"):
            dpi = 300 if ext in ("png", "jpg") else None
            fig.savefig(out_dir / f"{metric}_vs_scenario.{ext}", dpi=dpi)
        plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="Path to aggregated mobility_multichannel.csv")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="figures",
        help="Directory to save figures",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=None,
        help="Y-axis maximum for average delay plots",
    )
    parser.add_argument(
        "--max-energy",
        type=float,
        default=None,
        help="Y-axis maximum for energy plots",
    )
    args = parser.parse_args(argv)
    plot(args.csv, args.output_dir, args.max_delay, args.max_energy)


if __name__ == "__main__":
    main()
