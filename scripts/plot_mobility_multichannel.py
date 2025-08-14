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


def plot(csv_path: str, output_dir: str = "figures") -> None:
    df = pd.read_csv(csv_path)

    # Detect common column names
    scenario_col = None
    for name in ("scenario", "Scenario"):
        if name in df.columns:
            scenario_col = name
            break
    if scenario_col is None:
        raise ValueError("CSV must contain a 'scenario' column")

    delivered_col = next((c for c in df.columns if c.lower() == "delivered"), None)
    collisions_col = next((c for c in df.columns if c.lower() == "collisions"), None)
    if delivered_col is None or collisions_col is None:
        raise ValueError("CSV must contain 'delivered' and 'collisions' columns")

    total_packets = df[delivered_col] + df[collisions_col]

    # PDR may already be present in percent
    pdr_col = next((c for c in df.columns if c.lower().startswith("pdr")), None)
    if pdr_col:
        df["pdr"] = df[pdr_col]
    else:
        df["pdr"] = df[delivered_col] / total_packets * 100

    df["collision_rate"] = df[collisions_col] / total_packets * 100

    energy_col = next((c for c in df.columns if c.lower().startswith("energy")), None)
    nodes_col = next((c for c in df.columns if c.lower() == "nodes"), None)
    if energy_col and nodes_col:
        df["energy_per_node"] = df[energy_col] / df[nodes_col]

    grouped = df.groupby(scenario_col).mean(numeric_only=True)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # PDR vs scenario
    plt.figure()
    grouped["pdr"].plot(kind="bar", color="C0")
    plt.ylabel("PDR (%)")
    plt.title("PDR by scenario")
    plt.tight_layout()
    plt.savefig(out_dir / "pdr_vs_scenario.png")
    plt.close()

    # Collision rate vs scenario
    plt.figure()
    grouped["collision_rate"].plot(kind="bar", color="C1")
    plt.ylabel("Collision rate (%)")
    plt.title("Collision rate by scenario")
    plt.tight_layout()
    plt.savefig(out_dir / "collision_rate_vs_scenario.png")
    plt.close()

    # Average energy per node if available
    if "energy_per_node" in grouped:
        plt.figure()
        grouped["energy_per_node"].plot(kind="bar", color="C2")
        plt.ylabel("Average energy per node (J)")
        plt.title("Average energy per node by scenario")
        plt.tight_layout()
        plt.savefig(out_dir / "avg_energy_per_node_vs_scenario.png")
        plt.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="Path to aggregated mobility_multichannel.csv")
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
