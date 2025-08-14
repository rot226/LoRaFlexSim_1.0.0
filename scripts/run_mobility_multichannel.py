"""Run mobility and multi-channel simulation scenarios.

This utility executes four predefined scenarios combining mobile/static nodes
and single/three-channel configurations.  Metrics for each scenario are
collected and saved to a single CSV file under the ``results`` directory.

Usage::

    python scripts/run_mobility_multichannel.py --nodes 50 --packets 100 --seed 1
"""

import os
import sys
import argparse

# Allow running the script from a clone without installation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulateur_lora_sfrd.launcher import Simulator, MultiChannel  # noqa: E402

try:  # pandas is optional but required for CSV export
    import pandas as pd
except Exception as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(f"pandas is required for this script: {exc}")


RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def run_scenario(name: str, mobility: bool, channels: MultiChannel,
                 num_nodes: int, packets: int, seed: int) -> dict:
    """Run a single scenario and return its metrics."""
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
    metrics["scenario"] = name
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run mobility/static and multi-channel scenarios",
    )
    parser.add_argument("--nodes", type=int, default=50, help="Number of nodes")
    parser.add_argument("--packets", type=int, default=100,
                        help="Packets to send per node")
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

    runs = []
    for name, params in scenarios.items():
        runs.append(
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
    out_path = os.path.join(RESULTS_DIR, "mobility_multichannel.csv")
    pd.DataFrame(runs).to_csv(out_path, index=False)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
