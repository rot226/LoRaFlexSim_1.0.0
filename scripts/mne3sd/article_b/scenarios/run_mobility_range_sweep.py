"""Run a sweep over mobility models and communication ranges.

This scenario executes the :class:`loraflexsim.launcher.simulator.Simulator`
for the RandomWaypoint and SmoothMobility models while varying the
communication range expressed in kilometres.  For every combination of
``model`` and ``range_km`` the script runs several replicates, gathering a
selection of metrics including PDR, collision rate, latency, energy
consumption per node and the spreading factor distribution.

The per-replicate metrics together with aggregated mean and standard deviation
values are written to ``results/mne3sd/article_b/mobility_range_metrics.csv``.

Example usage::

    python scripts/mne3sd/article_b/scenarios/run_mobility_range_sweep.py \
        --nodes 200 --packets 50 --replicates 10 --seed 42
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable, Iterator

# Allow running the script from a clone without installation
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")),
)

from loraflexsim.launcher import RandomWaypoint, Simulator, SmoothMobility  # noqa: E402
from scripts.mne3sd.common import (
    add_execution_profile_argument,
    add_worker_argument,
    resolve_execution_profile,
    resolve_worker_count,
    summarise_metrics,
    write_csv,
)


DEFAULT_RANGES_KM = [5.0, 10.0, 15.0]
CI_RANGE_VALUES = [5.0]
CI_NODES = 40
CI_PACKETS = 10
CI_REPLICATES = 1
ROOT = Path(__file__).resolve().parents[4]
RESULTS_PATH = ROOT / "results" / "mne3sd" / "article_b" / "mobility_range_metrics.csv"

FIELDNAMES = [
    "model",
    "range_km",
    "area_size_m",
    "replicate",
    "pdr",
    "collision_rate",
    "avg_delay_s",
    "energy_per_node_J",
    "sf_distribution",
    "pdr_mean",
    "pdr_std",
    "collision_rate_mean",
    "collision_rate_std",
    "avg_delay_s_mean",
    "avg_delay_s_std",
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


def parse_range_list(
    values: Iterable[str] | None, *, default: Iterable[float] | None = None
) -> list[float]:
    """Parse ``--range-km`` entries into a unique ordered list of floats."""

    if not values:
        base = list(default) if default is not None else DEFAULT_RANGES_KM
        return [float(entry) for entry in base]

    ranges: list[float] = []
    seen: set[float] = set()

    def iter_parts(tokens: Iterable[str]) -> Iterator[str]:
        for token in tokens:
            for part in str(token).split(","):
                part = part.strip()
                if part:
                    yield part

    for part in iter_parts(values):
        distance = positive_float(part)
        if distance not in seen:
            ranges.append(distance)
            seen.add(distance)

    if not ranges:
        raise argparse.ArgumentTypeError("--range-km produced an empty list")

    return ranges


def normalise_sf_distribution(raw: dict) -> dict[str, float]:
    """Return a spreading factor distribution with normalised keys and floats."""

    distribution: dict[str, float] = {}
    for key, value in raw.items():
        try:
            sf_key = f"{int(key)}"
        except (TypeError, ValueError):
            sf_key = str(key)
        distribution[sf_key] = float(value)
    return distribution


def aggregate_sf_distribution(rows: list[dict[str, object]]) -> dict[str, float]:
    """Aggregate spreading factor distributions across replicates."""

    totals: dict[str, float] = {}
    for row in rows:
        distribution = row.get("sf_distribution_raw", {})
        if isinstance(distribution, dict):
            for key, value in distribution.items():
                sf_key = str(key)
                totals[sf_key] = totals.get(sf_key, 0.0) + float(value)

    total_packets = sum(totals.values())
    if total_packets == 0:
        return {}

    return {key: totals[key] / total_packets for key in sorted(totals)}


def _run_range_replicate(task: tuple) -> dict[str, object]:
    """Execute a single mobility range replicate and return its metrics."""

    (
        model_name,
        model_factory,
        range_km,
        area_size,
        replicate,
        seed,
        nodes,
        packets,
        interval,
        adr_node,
        adr_server,
    ) = task

    mobility_model = model_factory(area_size)
    sim = Simulator(
        num_nodes=nodes,
        num_gateways=1,
        packets_to_send=packets,
        seed=seed,
        mobility=True,
        mobility_model=mobility_model,
        area_size=area_size,
        packet_interval=interval,
        adr_node=adr_node,
        adr_server=adr_server,
    )
    sim.run()
    metrics = sim.get_metrics()

    delivered = int(metrics.get("delivered", 0))
    collisions = int(metrics.get("collisions", 0))
    total_packets = delivered + collisions
    collision_rate = collisions / total_packets if total_packets else 0.0

    energy_nodes = float(metrics.get("energy_nodes_J", 0.0))
    energy_per_node = energy_nodes / nodes if nodes else 0.0

    sf_distribution = normalise_sf_distribution(metrics.get("sf_distribution", {}))

    return {
        "model": model_name,
        "range_km": range_km,
        "area_size_m": area_size,
        "replicate": replicate,
        "pdr": float(metrics.get("PDR", 0.0)),
        "collision_rate": collision_rate,
        "avg_delay_s": float(metrics.get("avg_delay_s", 0.0)),
        "energy_per_node_J": energy_per_node,
        "sf_distribution": json.dumps(sf_distribution, sort_keys=True),
        "sf_distribution_raw": sf_distribution,
    }


def main() -> None:  # noqa: D401 - CLI entry point
    parser = argparse.ArgumentParser(
        description="Run a mobility range sweep for RandomWaypoint and SmoothMobility models",
    )
    parser.add_argument(
        "--range-km",
        action="append",
        help=(
            "Comma separated list of communication ranges in kilometres. Can be repeated. "
            "Defaults to 5,10,15 when omitted."
        ),
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
    add_worker_argument(parser)
    add_execution_profile_argument(parser)
    args = parser.parse_args()

    profile = resolve_execution_profile(args.profile)
    default_ranges = DEFAULT_RANGES_KM if profile != "ci" else CI_RANGE_VALUES
    range_values = parse_range_list(args.range_km, default=default_ranges)
    if profile == "ci" and args.range_km:
        range_values = range_values[:1]

    nodes = args.nodes if profile != "ci" else min(args.nodes, CI_NODES)
    packets = args.packets if profile != "ci" else min(args.packets, CI_PACKETS)
    replicates = args.replicates if profile != "ci" else CI_REPLICATES
    workers = resolve_worker_count(args.workers, replicates)

    models = [
        ("random_waypoint", RandomWaypoint),
        ("smooth", SmoothMobility),
    ]

    results: list[dict[str, object]] = []
    combination_index = 0

    executor: ProcessPoolExecutor | None = None
    if workers > 1:
        executor = ProcessPoolExecutor(max_workers=workers)

    try:
        for model_name, model_factory in models:
            for range_km in range_values:
                area_size = range_km * 2000.0
                tasks = [
                    (
                        model_name,
                        model_factory,
                        range_km,
                        area_size,
                        replicate,
                        args.seed + combination_index * replicates + replicate - 1,
                        nodes,
                        packets,
                        args.interval,
                        args.adr_node,
                        args.adr_server,
                    )
                    for replicate in range(1, replicates + 1)
                ]

                if executor is not None:
                    replicate_rows = list(executor.map(_run_range_replicate, tasks, chunksize=1))
                else:
                    replicate_rows = [_run_range_replicate(task) for task in tasks]

                replicate_rows.sort(key=lambda row: int(row["replicate"]))

                combination_index += 1

                results.extend(
                    {
                        key: value
                        for key, value in row.items()
                        if key != "sf_distribution_raw"
                    }
                    for row in replicate_rows
                )

                summary_entries = summarise_metrics(
                    replicate_rows,
                    ["model", "range_km", "area_size_m"],
                    ["pdr", "collision_rate", "avg_delay_s", "energy_per_node_J"],
                )
                sf_summary = aggregate_sf_distribution(replicate_rows)
                sf_json = json.dumps(sf_summary, sort_keys=True)

                for entry in summary_entries:
                    summary_row: dict[str, object] = {
                        "model": entry["model"],
                        "range_km": entry["range_km"],
                        "area_size_m": entry["area_size_m"],
                        "replicate": "aggregate",
                        "sf_distribution": sf_json,
                    }
                    for metric in ("pdr", "collision_rate", "avg_delay_s", "energy_per_node_J"):
                        summary_row[f"{metric}_mean"] = entry.get(f"{metric}_mean", "")
                        summary_row[f"{metric}_std"] = entry.get(f"{metric}_std", "")
                    results.append(summary_row)
    finally:
        if executor is not None:
            executor.shutdown()

    write_csv(RESULTS_PATH, FIELDNAMES, results)

    print(f"Results saved to {RESULTS_PATH}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
