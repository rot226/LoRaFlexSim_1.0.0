"""Run mobility and multi-channel simulation scenarios.

This utility executes four predefined scenarios combining mobile/static nodes
and single/multi-channel configurations.  The number of channels may be chosen
among 1, 3 or 6 via ``--channels`` and additional options expose node count,
packet interval, mobility speed and area size.  Each scenario may be repeated
using ``--replicates`` and the mean/standard deviation of key metrics are
stored in ``results/mobility_multichannel.csv``.

Usage::

    python scripts/run_mobility_multichannel.py --nodes 50 --packets 100 --seed 1
    # or run a congested configuration
    python scripts/run_mobility_multichannel.py --high-traffic --replicates 5
"""

import os
import sys
import argparse
from typing import List

# Allow running the script from a clone without installation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulateur_lora_sfrd.launcher import Simulator, MultiChannel  # noqa: E402

try:  # pandas is optional but required for CSV export
    import pandas as pd
except Exception as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(f"pandas is required for this script: {exc}")


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
    """Run a single scenario and return its metrics."""
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
    metrics["scenario"] = name
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run mobility/static and multi-channel scenarios",
    )
    parser.add_argument("--nodes", type=int, default=50, help="Number of nodes")
    parser.add_argument(
        "--packets", type=int, default=100, help="Packets to send per node"
    )
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
        default=5,
        help="Number of simulation replicates (>=5)",
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

    if args.replicates < 5:
        parser.error("--replicates must be at least 5")

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

    rows: List[dict] = []
    for name, params in scenarios.items():
        replicates = []
        for r in range(args.replicates):
            replicates.append(
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

        df = pd.DataFrame(replicates)
        total_packets = df["delivered"] + df["collisions"]
        df["pdr"] = df["delivered"] / total_packets * 100
        df["collision_rate"] = df["collisions"] / total_packets * 100
        df["energy_per_node"] = df["energy_nodes_J"] / args.nodes

        stats = {
            "scenario": name,
            "nodes": args.nodes,
            "packets": args.packets,
            "interval": args.interval,
            "area_size": args.area_size,
            "speed": args.speed,
            "channels": len(params["channels"].channels),
            "adr_node": args.adr_node,
            "adr_server": args.adr_server,
        }
        for col in ["pdr", "collision_rate", "avg_delay_s", "energy_per_node"]:
            mean = df[col].mean()
            std = df[col].std(ddof=0)
            stats[f"{col}_mean"] = mean
            stats[f"{col}_std"] = std
        rows.append(stats)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "mobility_multichannel.csv")
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
