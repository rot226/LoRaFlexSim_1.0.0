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
    pdr = [float(row["pdr_mean"]) * 100 for row in reader]
    pdr_err = [float(row.get("pdr_std", 0)) * 100 for row in reader]
    avg_delay = [float(row["avg_delay_mean"]) for row in reader]
    avg_delay_err = [float(row.get("avg_delay_std", 0)) for row in reader]
    energy_per_node = [float(row["energy_per_node_mean"]) for row in reader]
    energy_err = [float(row.get("energy_per_node_std", 0)) for row in reader]
    collision_rate = [float(row.get("collision_rate_mean", 0)) * 100 for row in reader]
    collision_err = [float(row.get("collision_rate_std", 0)) * 100 for row in reader]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # PDR vs scenario
    plt.figure()
    plt.bar(scenarios, pdr, yerr=pdr_err, color="C0", capsize=4)
    plt.ylabel("PDR (%)")
    plt.title("PDR by scenario")
    plt.tight_layout()
    plt.savefig(out_dir / "pdr_vs_scenario.svg")
    plt.close()

    # Average delay vs scenario
    plt.figure()
    plt.bar(scenarios, avg_delay, yerr=avg_delay_err, color="C1", capsize=4)
    plt.ylabel("Average delay (s)")
    plt.title("Average delay by scenario")
    plt.tight_layout()
    plt.savefig(out_dir / "avg_delay_vs_scenario.svg")
    plt.close()

    # Average energy per node vs scenario
    plt.figure()
    plt.bar(scenarios, energy_per_node, yerr=energy_err, color="C2", capsize=4)
    plt.ylabel("Average energy per node (J)")
    plt.title("Average energy per node by scenario")
    plt.tight_layout()
    plt.savefig(out_dir / "avg_energy_per_node_vs_scenario.svg")
    plt.close()

    # Collision rate vs scenario if available
    if any(collision_rate):
        plt.figure()
        plt.bar(
            scenarios,
            collision_rate,
            yerr=collision_err,
            color="C3",
            capsize=4,
        )
        plt.ylabel("Collision rate (%)")
        plt.title("Collision rate by scenario")
        plt.tight_layout()
        plt.savefig(out_dir / "collision_rate_vs_scenario.svg")
        plt.close()


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
