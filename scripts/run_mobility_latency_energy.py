"""Run mobility/static and single/three-channel scenarios to collect latency, energy and PDR.

This utility executes four predefined scenarios combining mobile/static nodes
and mono/multi-channel configurations.  The number of channels can be selected
from 1, 3 or 6 with ``--channels`` and additional options expose node count,
packet interval, mobility speed and area size.  Scenarios may be repeated via
``--replicates`` and the mean/standard deviation of PDR, delay, collision rate
and energy per node are written to ``results/mobility_latency_energy.csv``.

Usage::

    python scripts/run_mobility_latency_energy.py --nodes 50 --packets 100 --seed 1
"""

from __future__ import annotations

import argparse
import os
import sys
import csv
import statistics

# Allow running the script from a clone without installation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loraflexsim.launcher import MultiChannel, Simulator  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def run_scenario(
    name: str,
    mobility: bool,
    channels: MultiChannel,
    num_nodes: int,
    packets: int,
    seed: int,
    adr_node: bool,
    adr_server: bool,
    area_size: float,
    interval: float,
    speed: float,
) -> dict:
    """Run a single scenario and return selected metrics."""
    sim = Simulator(
        num_nodes=num_nodes,
        num_gateways=1,
        packets_to_send=packets,
        seed=seed,
        mobility=mobility,
        channels=channels,
        adr_node=adr_node,
        adr_server=adr_server,
        area_size=area_size,
        packet_interval=interval,
        mobility_speed=(speed, speed),
    )
    sim.run()
    metrics = sim.get_metrics()
    total_packets = metrics["delivered"] + metrics["collisions"]
    return {
        "scenario": name,
        "pdr": metrics["PDR"] * 100,
        "avg_delay": metrics["avg_delay_s"],
        "energy_per_node": metrics["energy_nodes_J"] / num_nodes,
        "collision_rate": metrics["collisions"] / total_packets * 100
        if total_packets
        else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run mobility/static and mono/tri-channel scenarios",
    )
    parser.add_argument("--nodes", type=int, default=50, help="Number of nodes")
    parser.add_argument("--packets", type=int, default=100, help="Packets per node")
    parser.add_argument("--seed", type=int, default=1, help="Random seed")
    parser.add_argument(
        "--adr-node",
        action="store_true",
        help="Enable ADR algorithm on nodes",
    )
    parser.add_argument(
        "--adr-server",
        action="store_true",
        help="Enable ADR algorithm on server",
    )
    parser.add_argument(
        "--area-size",
        type=float,
        default=1000.0,
        help="Square area size in metres",
    )
    parser.add_argument(
        "--interval", type=float, default=60.0, help="Mean packet interval (s)"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=5.0,
        help="Mobility speed for nodes (m/s)",
    )
    parser.add_argument(
        "--channels",
        type=int,
        choices=[1, 3, 6],
        default=3,
        help="Number of channels for multi-channel scenarios",
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=1,
        help="Number of simulation replicates",
    )
    parser.add_argument(
        "--high-traffic",
        action="store_true",
        help="Shortcut enabling congested conditions (nodes=200, interval=1s, area=500m)",
    )
    args = parser.parse_args()

    if args.high_traffic:
        if args.nodes == parser.get_default("nodes"):
            args.nodes = 200
        if args.interval == parser.get_default("interval"):
            args.interval = 1.0
        if args.area_size == parser.get_default("area_size"):
            args.area_size = 500.0

    freq_plan = [
        868100000.0,
        868300000.0,
        868500000.0,
        867100000.0,
        867300000.0,
        867500000.0,
    ]
    scenarios = {
        "static_single": {
            "mobility": False,
            "channels": MultiChannel(freq_plan[:1]),
        },
        "static_multi": {
            "mobility": False,
            "channels": MultiChannel(freq_plan[: args.channels]),
        },
        "mobile_single": {
            "mobility": True,
            "channels": MultiChannel(freq_plan[:1]),
        },
        "mobile_multi": {
            "mobility": True,
            "channels": MultiChannel(freq_plan[: args.channels]),
        },
    }

    rows: list[dict] = []
    for name, params in scenarios.items():
        rep_rows = []
        for r in range(args.replicates):
            rep_rows.append(
                run_scenario(
                    name,
                    params["mobility"],
                    params["channels"],
                    args.nodes,
                    args.packets,
                    args.seed + r,
                    args.adr_node,
                    args.adr_server,
                    args.area_size,
                    args.interval,
                    args.speed,
                )
            )

        agg = {
            "scenario": name,
            "nodes": args.nodes,
            "interval": args.interval,
            "area_size": args.area_size,
            "speed": args.speed,
            "channels": len(params["channels"].channels),
        }
        for key in ["pdr", "avg_delay", "energy_per_node", "collision_rate"]:
            values = [row[key] for row in rep_rows]
            agg[f"{key}_mean"] = statistics.mean(values)
            agg[f"{key}_std"] = statistics.pstdev(values)
        rows.append(agg)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "mobility_latency_energy.csv")
    fieldnames = [
        "scenario",
        "nodes",
        "interval",
        "area_size",
        "speed",
        "channels",
        "pdr_mean",
        "pdr_std",
        "avg_delay_mean",
        "avg_delay_std",
        "energy_per_node_mean",
        "energy_per_node_std",
        "collision_rate_mean",
        "collision_rate_std",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
