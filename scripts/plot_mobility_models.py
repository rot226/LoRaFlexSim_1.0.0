"""Plot metrics comparing mobility models from mobility_models.csv.

Usage::

    python scripts/plot_mobility_models.py results/mobility_models.csv
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

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = [
        ("pdr", "PDR", "%", "%.1f%%", "C0"),
        ("avg_delay", "Average delay", "s", "%.2f s", "C2"),
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
        x = range(len(df["model"]))
        bars = ax.bar(
            x,
            df[mean_col],
            yerr=yerr,
            capsize=4,
            color=color,
            label=label,
        )
        ax.set_xlabel("Mobility model")
        ax.set_xticks(x)
        ax.set_xticklabels(df["model"], rotation=45, ha="right")
        ax.set_ylabel(label)

        if metric == "pdr":
            cap = 100.0
            ax.set_ylim(0, cap)
            ax.axhline(cap, linestyle="--", color="grey", label="100 %")
        elif metric == "avg_delay":
            cap = max_delay or df[mean_col].max() * 1.1
            ax.set_ylim(0, cap)
        elif metric == "energy_per_node":
            cap = max_energy or df[mean_col].max() * 1.1
            ax.set_ylim(0, cap)
        else:
            cap = df[mean_col].max() * 1.1
            ax.set_ylim(0, cap)

        ax.set_title(f"{name} by model (0 ≤ {name} ≤ {cap:g} {unit})")
        ax.bar_label(bars, fmt=fmt, label_type="center")
        ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
        fig.tight_layout(rect=[0, 0.2, 0.9, 1])
        for ext in ("png", "jpg", "eps"):
            dpi = 300 if ext in ("png", "jpg") else None
            fig.savefig(out_dir / f"{metric}_vs_model.{ext}", dpi=dpi)
        plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="Path to mobility_models.csv")
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
