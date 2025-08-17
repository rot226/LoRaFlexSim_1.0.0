"""Run mobility/static and single/three-channel scenarios to collect latency, energy and PDR.

This utility executes four predefined scenarios combining mobile/static nodes
and mono/tri-channel configurations. Metrics for each scenario are aggregated
into ``results/mobility_latency_energy.csv`` with columns:
``scenario``, ``pdr``, ``avg_delay`` (seconds) and ``energy_per_node`` (J).

Usage::

    python scripts/run_mobility_latency_energy.py --nodes 50 --packets 100 --seed 1
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running the script from a clone without installation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulateur_lora_sfrd.launcher import MultiChannel, Simulator  # noqa: E402
import csv

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def run_scenario(
    name: str,
    mobility: bool,
    channels: MultiChannel,
    num_nodes: int,
    packets: int,
    seed: int,
) -> dict:
    """Run a single scenario and return selected metrics."""
    sim = Simulator(
        num_nodes=num_nodes,
        num_gateways=1,
        packets_to_send=packets,
        seed=seed,
        mobility=mobility,
        channels=channels,
    )
    sim.run()
    metrics = sim.get_metrics()
    return {
        "scenario": name,
        "pdr": metrics["PDR"],
        "avg_delay": metrics["avg_delay_s"],
        "energy_per_node": metrics["energy_nodes_J"] / num_nodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run mobility/static and mono/tri-channel scenarios",
    )
    parser.add_argument("--nodes", type=int, default=50, help="Number of nodes")
    parser.add_argument("--packets", type=int, default=100, help="Packets per node")
    parser.add_argument("--seed", type=int, default=1, help="Random seed")
    args = parser.parse_args()

    scenarios = {
        "static_single": {
            "mobility": False,
            "channels": MultiChannel([868100000.0]),
        },
        "static_three": {
            "mobility": False,
            "channels": MultiChannel([868100000.0, 868300000.0, 868500000.0]),
        },
        "mobile_single": {
            "mobility": True,
            "channels": MultiChannel([868100000.0]),
        },
        "mobile_three": {
            "mobility": True,
            "channels": MultiChannel([868100000.0, 868300000.0, 868500000.0]),
        },
    }

    rows: list[dict] = []
    for name, params in scenarios.items():
        rows.append(
            run_scenario(
                name,
                params["mobility"],
                params["channels"],
                args.nodes,
                args.packets,
                args.seed,
            )
        )

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "mobility_latency_energy.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["scenario", "pdr", "avg_delay", "energy_per_node"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
