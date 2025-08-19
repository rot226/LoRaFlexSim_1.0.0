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
    df.columns = [c.lower() for c in df.columns]
    if "scenario" not in df.columns:
        raise ValueError("CSV must contain a 'scenario' column")
    df = df.set_index("scenario")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # PDR with error bars
    if "pdr_mean" in df:
        plt.figure()
        plt.bar(
            df.index,
            df["pdr_mean"] * 100,
            yerr=df.get("pdr_std", 0) * 100,
            color="C0",
            capsize=4,
        )
        plt.ylabel("PDR (%)")
        plt.title("PDR by scenario")
        plt.tight_layout()
        plt.savefig(out_dir / "pdr_vs_scenario.png")
        plt.close()

    # Collision rate with error bars
    if "collision_rate_mean" in df:
        plt.figure()
        plt.bar(
            df.index,
            df["collision_rate_mean"] * 100,
            yerr=df.get("collision_rate_std", 0) * 100,
            color="C1",
            capsize=4,
        )
        plt.ylabel("Collision rate (%)")
        plt.title("Collision rate by scenario")
        plt.tight_layout()
        plt.savefig(out_dir / "collision_rate_vs_scenario.png")
        plt.close()

    # Average delay if available
    if "avg_delay_s_mean" in df:
        plt.figure()
        plt.bar(
            df.index,
            df["avg_delay_s_mean"],
            yerr=df.get("avg_delay_s_std", 0),
            color="C2",
            capsize=4,
        )
        plt.ylabel("Average delay (s)")
        plt.title("Average delay by scenario")
        plt.tight_layout()
        plt.savefig(out_dir / "avg_delay_vs_scenario.png")
        plt.close()

    # Average energy per node
    if "energy_per_node_mean" in df:
        plt.figure()
        plt.bar(
            df.index,
            df["energy_per_node_mean"],
            yerr=df.get("energy_per_node_std", 0),
            color="C3",
            capsize=4,
        )
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
