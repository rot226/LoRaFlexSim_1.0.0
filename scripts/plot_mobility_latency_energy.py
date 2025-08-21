#!/usr/bin/env python3
"""Plot PDR, latency and energy metrics from mobility_latency_energy.csv.

Usage::

    python scripts/plot_mobility_latency_energy.py results/mobility_latency_energy.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot(csv_path: str, output_dir: str = "figures") -> None:
    df = pd.read_csv(csv_path)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = [
        ("pdr", "PDR (%)", "%.1f%%", "C0", "pdr_vs_scenario.svg"),
        ("avg_delay", "Average delay (s)", "%.2f s", "C1", "avg_delay_vs_scenario.svg"),
        (
            "energy_per_node",
            "Average energy per node (J)",
            "%.2f J",
            "C2",
            "avg_energy_per_node_vs_scenario.svg",
        ),
        (
            "collision_rate",
            "Collision rate (%)",
            "%.1f%%",
            "C3",
            "collision_rate_vs_scenario.svg",
        ),
    ]

    for metric, ylabel, fmt, color, filename in metrics:
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
            label=ylabel,
        )
        ax.set_xlabel("Scenario")
        ax.set_ylabel(ylabel)
        ax.set_title(f"{ylabel} by scenario")
        ax.bar_label(bars, fmt=fmt, label_type="center")
        ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
        fig.tight_layout(rect=[0, 0, 0.85, 1])
        fig.savefig(out_dir / filename)
        plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="Path to mobility_latency_energy.csv")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="figures",
        help="Directory to save figures",
    )
    args = parser.parse_args(argv)
    plot(args.csv, args.output_dir)


if __name__ == "__main__":
    main()
