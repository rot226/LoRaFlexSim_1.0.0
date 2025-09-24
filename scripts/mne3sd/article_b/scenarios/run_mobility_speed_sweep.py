"""Run a sweep over mobility models and speed profiles.

This scenario executes the :class:`loraflexsim.launcher.simulator.Simulator`
for the RandomWaypoint and SmoothMobility models while varying the mobility
speed bounds provided through ``--speed-profiles``.  For each combination of
``model`` and ``speed_profile`` the script runs several replicates, gathering a
selection of metrics including packet delivery ratio (PDR), mean end-to-end
latency, latency jitter (standard deviation of per-packet delays) and the mean
energy consumption per node.

Aggregated mean and standard deviation statistics are appended to
``results/mne3sd/article_b/mobility_speed_metrics.csv``.

Example usage::

    python scripts/mne3sd/article_b/scenarios/run_mobility_speed_sweep.py \
        --nodes 200 --replicates 10 --seed 42 \
        --speed-profiles "pedestrian: (0.5, 1.5)" \
        --speed-profiles "urban: (1.5, 3.5)"
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from pathlib import Path
from typing import Iterable

# Allow running the script from a clone without installation
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")),
)

from loraflexsim.launcher import RandomWaypoint, Simulator, SmoothMobility  # noqa: E402
from scripts.mne3sd.common import summarise_metrics, write_csv

DEFAULT_SPEED_PROFILES: list[tuple[str, tuple[float, float]]] = [
    ("pedestrian", (0.5, 1.5)),
    ("urban", (1.5, 3.5)),
    ("vehicular", (5.0, 15.0)),
]

ROOT = Path(__file__).resolve().parents[4]
RESULTS_PATH = ROOT / "results" / "mne3sd" / "article_b" / "mobility_speed_metrics.csv"

FIELDNAMES = [
    "model",
    "speed_profile",
    "speed_min_mps",
    "speed_max_mps",
    "replicate",
    "pdr",
    "avg_delay_s",
    "jitter_s",
    "energy_per_node_J",
    "pdr_mean",
    "pdr_std",
    "avg_delay_s_mean",
    "avg_delay_s_std",
    "jitter_s_mean",
    "jitter_s_std",
    "energy_per_node_J_mean",
    "energy_per_node_J_std",
]


def positive_int(value: str) -> int:
    """Return ``value`` converted to a strictly positive integer."""

    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return number


def positive_float(value: str) -> float:
    """Return ``value`` converted to a strictly positive float."""

    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def parse_speed_profiles(values: Iterable[str] | None) -> list[tuple[str, tuple[float, float]]]:
    """Parse ``--speed-profiles`` entries into an ordered list of tuples."""

    if not values:
        return DEFAULT_SPEED_PROFILES.copy()

    profiles: list[tuple[str, tuple[float, float]]] = []
    seen: set[str] = set()

    for raw in values:
        if not raw:
            continue
        name_part, sep, range_part = raw.partition(":")
        if not sep:
            raise argparse.ArgumentTypeError(
                "speed profile entries must follow the 'name: (min, max)' format"
            )
        name = name_part.strip()
        if not name:
            raise argparse.ArgumentTypeError("speed profile name cannot be empty")
        range_str = range_part.strip()
        if range_str.startswith("(") and range_str.endswith(")"):
            range_str = range_str[1:-1]
        tokens = [token for token in range_str.replace(",", " ").split() if token]
        if len(tokens) != 2:
            raise argparse.ArgumentTypeError(
                "speed profile bounds must contain exactly two numeric values"
            )
        speed_min = positive_float(tokens[0])
        speed_max = positive_float(tokens[1])
        if speed_min > speed_max:
            raise argparse.ArgumentTypeError("minimum speed cannot exceed maximum speed")
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        profiles.append((name, (speed_min, speed_max)))

    if not profiles:
        raise argparse.ArgumentTypeError("--speed-profiles produced an empty list")

    return profiles


def compute_latency_jitter(sim: Simulator) -> float:
    """Return the standard deviation of successful packet delays."""

    delays = [
        float(entry["end_time"]) - float(entry["start_time"])
        for entry in sim.events_log
        if entry.get("result") == "Success"
    ]
    if len(delays) > 1:
        return statistics.pstdev(delays)
    return 0.0


def main() -> None:  # noqa: D401 - CLI entry point
    parser = argparse.ArgumentParser(
        description=(
            "Run a mobility speed sweep for RandomWaypoint and SmoothMobility models"
        ),
    )
    parser.add_argument(
        "--speed-profiles",
        action="append",
        help=(
            "Speed profile definitions in the form 'name: (min, max)'. Can be repeated. "
            "Defaults to pedestrian, urban and vehicular profiles when omitted."
        ),
    )
    parser.add_argument(
        "--range-km",
        type=positive_float,
        default=10.0,
        help="Communication range expressed in kilometres used to derive the area size",
    )
    parser.add_argument("--nodes", type=positive_int, default=100, help="Number of end devices")
    parser.add_argument(
        "--packets",
        type=positive_int,
        default=50,
        help="Number of packets each node should transmit",
    )
    parser.add_argument(
        "--replicates",
        type=positive_int,
        default=5,
        help="Number of simulation replicates for each configuration",
    )
    parser.add_argument("--seed", type=int, default=1, help="Base random seed")
    parser.add_argument(
        "--interval",
        type=positive_float,
        default=300.0,
        help="Mean packet interval in seconds",
    )
    parser.add_argument("--adr-node", action="store_true", help="Enable ADR on the devices")
    parser.add_argument("--adr-server", action="store_true", help="Enable ADR on the server")
    args = parser.parse_args()

    speed_profiles = parse_speed_profiles(args.speed_profiles)
    area_size = args.range_km * 2000.0

    models = [
        ("random_waypoint", RandomWaypoint),
        ("smooth", SmoothMobility),
    ]

    results: list[dict[str, float | str]] = []
    combination_index = 0

    for model_name, model_factory in models:
        for profile_name, (speed_min, speed_max) in speed_profiles:
            replicate_rows: list[dict[str, float | str]] = []

            for replicate in range(1, args.replicates + 1):
                seed = args.seed + combination_index * args.replicates + replicate - 1
                mobility_model = model_factory(
                    area_size,
                    min_speed=speed_min,
                    max_speed=speed_max,
                )
                sim = Simulator(
                    num_nodes=args.nodes,
                    num_gateways=1,
                    packets_to_send=args.packets,
                    seed=seed,
                    mobility=True,
                    mobility_model=mobility_model,
                    area_size=area_size,
                    mobility_speed=(speed_min, speed_max),
                    packet_interval=args.interval,
                    adr_node=args.adr_node,
                    adr_server=args.adr_server,
                )
                sim.run()
                metrics = sim.get_metrics()

                energy_nodes = float(metrics.get("energy_nodes_J", 0.0))
                energy_per_node = energy_nodes / args.nodes if args.nodes else 0.0

                replicate_rows.append(
                    {
                        "model": model_name,
                        "speed_profile": profile_name,
                        "speed_min_mps": speed_min,
                        "speed_max_mps": speed_max,
                        "replicate": replicate,
                        "pdr": float(metrics.get("PDR", 0.0)),
                        "avg_delay_s": float(metrics.get("avg_delay_s", 0.0)),
                        "jitter_s": compute_latency_jitter(sim),
                        "energy_per_node_J": energy_per_node,
                    }
                )

            combination_index += 1

            results.extend(replicate_rows)

            summary_entries = summarise_metrics(
                replicate_rows,
                ["model", "speed_profile", "speed_min_mps", "speed_max_mps"],
                ["pdr", "avg_delay_s", "jitter_s", "energy_per_node_J"],
            )
            for entry in summary_entries:
                aggregate_row: dict[str, float | str] = {
                    "model": entry["model"],
                    "speed_profile": entry["speed_profile"],
                    "speed_min_mps": entry["speed_min_mps"],
                    "speed_max_mps": entry["speed_max_mps"],
                    "replicate": "aggregate",
                }
                for metric in ("pdr", "avg_delay_s", "jitter_s", "energy_per_node_J"):
                    aggregate_row[f"{metric}_mean"] = entry.get(f"{metric}_mean", "")
                    aggregate_row[f"{metric}_std"] = entry.get(f"{metric}_std", "")
                results.append(aggregate_row)

    write_csv(RESULTS_PATH, FIELDNAMES, results)

    print(f"Results saved to {RESULTS_PATH}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
