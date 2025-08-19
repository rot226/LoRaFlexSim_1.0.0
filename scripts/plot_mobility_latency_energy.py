#!/usr/bin/env python3
"""Plot PDR, latency and energy metrics from mobility_latency_energy.csv.

Usage::

    python scripts/plot_mobility_latency_energy.py results/mobility_latency_energy.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import csv


def plot(csv_path: str, output_dir: str = "figures") -> None:
    with open(csv_path, newline="") as f:
        reader = list(csv.DictReader(f))

    if not reader:
        raise ValueError("CSV contains no data")

    scenarios = [row["scenario"] for row in reader]
    pdr = [float(row["pdr"]) * 100 for row in reader]
    avg_delay = [float(row["avg_delay"]) for row in reader]
    energy_per_node = [float(row["energy_per_node"]) for row in reader]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # PDR vs scenario
    fig, ax = plt.subplots()
    bars = ax.bar(scenarios, pdr, color="C0")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("PDR (%)")
    ax.set_title("PDR by scenario")
    ax.bar_label(bars, fmt="%.1f%%")
    fig.tight_layout()
    fig.savefig(out_dir / "pdr_vs_scenario.svg")
    plt.close(fig)

    # Average delay vs scenario
    fig, ax = plt.subplots()
    bars = ax.bar(scenarios, avg_delay, color="C1")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Average delay (s)")
    ax.set_title("Average delay by scenario")
    ax.bar_label(bars, fmt="%.2f s")
    fig.tight_layout()
    fig.savefig(out_dir / "avg_delay_vs_scenario.svg")
    plt.close(fig)

    # Average energy per node vs scenario
    fig, ax = plt.subplots()
    bars = ax.bar(scenarios, energy_per_node, color="C2")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Average energy per node (J)")
    ax.set_title("Average energy per node by scenario")
    ax.bar_label(bars, fmt="%.2f J")
    fig.tight_layout()
    fig.savefig(out_dir / "avg_energy_per_node_vs_scenario.svg")
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
