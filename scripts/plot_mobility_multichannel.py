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

    params = []
    if "nodes" in df.columns:
        params.append(f"nodes={int(df['nodes'].iloc[0])}")
    if "interval" in df.columns:
        params.append(f"interval={df['interval'].iloc[0]:g}s")
    if "speed" in df.columns:
        params.append(f"speed={df['speed'].iloc[0]:g}m/s")
    if "area_size" in df.columns:
        params.append(f"area={df['area_size'].iloc[0]:g}m²")
    if "channels" in df.columns:
        params.append(f"channels={int(df['channels'].iloc[0])}")
    param_text = ", ".join(params)

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
        fig, ax = plt.subplots(figsize=(12, 6))
        label = f"{name} ({unit})"
        bars = ax.bar(
            df["scenario"],
            df[mean_col],
            yerr=yerr,
            capsize=4,
            color=color,
            label=label,
        )
        ax.set_xlabel("Scenario")
        ax.set_xticks(range(len(df["scenario"])))
        ax.set_xticklabels(df["scenario"], rotation=45, ha="right")
        ax.set_ylabel(label)

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
        if param_text:
            title += f"\n{param_text}"
        ax.set_title(title)
        ax.bar_label(bars, fmt=fmt, label_type="center")
        ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
        fig.tight_layout(rect=[0, 0.2, 0.9, 1])
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
