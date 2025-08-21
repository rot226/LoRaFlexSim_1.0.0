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

    if "scenario" not in df.columns:
        raise ValueError("CSV must contain a 'scenario' column")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "pdr": ("PDR (%)", "%.1f%%", "C0"),
        "collision_rate": ("Collision rate (%)", "%.1f%%", "C1"),
        "avg_delay_s": ("Average delay (s)", "%.2f s", "C2"),
        "energy_per_node": (
            "Average energy per node (J)",
            "%.2f J",
            "C3",
        ),
    }

    for metric, (ylabel, fmt, color) in metrics.items():
        mean_col = f"{metric}_mean"
        std_col = f"{metric}_std"
        if mean_col not in df.columns:
            continue
        fig, ax = plt.subplots()
        bars = ax.bar(
            df["scenario"],
            df[mean_col],
            yerr=df[std_col],
            capsize=4,
            color=color,
        )
        ax.set_xlabel("Scenario")

        name, unit = ylabel.split(" (")
        unit = unit.rstrip(")")
        if metric in {"pdr", "collision_rate"}:
            ax.set_ylim(0, 100)
            ax.axhline(100, linestyle="--", color="grey", label="100 %")
            ax.legend()
            upper = "100 %"
        elif metric.startswith("avg_delay"):
            upper_val = max_delay if max_delay is not None else df[mean_col].max() * 1.1
            ax.set_ylim(0, upper_val)
            upper = f"{upper_val:.2f} {unit}"
        elif metric == "energy_per_node":
            upper_val = max_energy if max_energy is not None else df[mean_col].max() * 1.1
            ax.set_ylim(0, upper_val)
            upper = f"{upper_val:.2f} {unit}"
        else:
            upper = ""

        ax.set_ylabel(ylabel)
        ax.set_title(f"{ylabel} by scenario\n0 \u2264 {name} \u2264 {upper}")
        ax.bar_label(bars, fmt=fmt)
        fig.tight_layout()
        fig.savefig(out_dir / f"{metric}_vs_scenario.png")
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
        help="Maximum y value for average delay plot",
    )
    parser.add_argument(
        "--max-energy",
        type=float,
        default=None,
        help="Maximum y value for energy plot",
    )
    args = parser.parse_args(argv)
    plot(args.csv, args.output_dir, args.max_delay, args.max_energy)


if __name__ == "__main__":
    main()
