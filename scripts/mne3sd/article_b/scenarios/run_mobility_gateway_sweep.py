"""Run mobility scenarios sweeping the number of gateways.

This scenario executes the :class:`loraflexsim.launcher.simulator.Simulator`
for the RandomWaypoint and SmoothMobility models while varying the number of
available gateways.  For every combination of ``model`` and ``num_gateways``
the script runs several replicates, gathering Packet Delivery Ratio (PDR),
collision rate, the mean downlink delay when available and the share of
uplink packets collected by each gateway.

The per-replicate metrics together with aggregated mean and standard deviation
values are written to
``results/mne3sd/article_b/mobility_gateway_metrics.csv``.

Example usage::

    python scripts/mne3sd/article_b/scenarios/run_mobility_gateway_sweep.py \
        --gateways-list 1,2,4 --nodes 200 --replicates 10 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import types
from pathlib import Path
from typing import Iterable, Iterator

# Allow running the script from a clone without installation
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")),
)

from loraflexsim.launcher import (  # noqa: E402
    MultiChannel,
    RandomWaypoint,
    Simulator,
    SmoothMobility,
)

DEFAULT_CHANNELS = [
    868_100_000.0,
    868_300_000.0,
    868_500_000.0,
]
DEFAULT_GATEWAYS = [1, 2, 4]
ROOT = Path(__file__).resolve().parents[4]
RESULTS_PATH = ROOT / "results" / "mne3sd" / "article_b" / "mobility_gateway_metrics.csv"

FIELDNAMES = [
    "model",
    "gateways",
    "range_km",
    "area_size_m",
    "nodes",
    "channels",
    "replicate",
    "seed",
    "pdr",
    "collision_rate",
    "avg_downlink_delay_s",
    "downlink_samples",
    "pdr_by_gateway",
    "pdr_mean",
    "pdr_std",
    "collision_rate_mean",
    "collision_rate_std",
    "avg_downlink_delay_s_mean",
    "avg_downlink_delay_s_std",
    "pdr_by_gateway_mean",
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


def parse_gateways_list(values: Iterable[str] | None) -> list[int]:
    """Parse ``--gateways-list`` entries into a unique ordered list of integers."""

    if not values:
        return DEFAULT_GATEWAYS.copy()

    gateways: list[int] = []
    seen: set[int] = set()

    def iter_parts(tokens: Iterable[str]) -> Iterator[str]:
        for token in tokens:
            for part in str(token).split(","):
                part = part.strip()
                if part:
                    yield part

    for part in iter_parts(values):
        number = positive_int(part)
        if number not in seen:
            gateways.append(number)
            seen.add(number)

    if not gateways:
        raise argparse.ArgumentTypeError("--gateways-list produced an empty list")

    return gateways


def parse_channel_frequencies(values: Iterable[str] | None) -> list[float]:
    """Parse ``--channels`` entries into an ordered list of frequencies."""

    if not values:
        return DEFAULT_CHANNELS.copy()

    channels: list[float] = []
    seen: set[float] = set()

    def iter_parts(tokens: Iterable[str]) -> Iterator[str]:
        for token in tokens:
            for part in str(token).replace(";", ",").split(","):
                part = part.strip()
                if part:
                    yield part

    for part in iter_parts(values):
        try:
            frequency = float(part)
        except ValueError as exc:  # pragma: no cover - handled during CLI parsing
            raise argparse.ArgumentTypeError(f"invalid channel frequency: {part}") from exc
        if frequency <= 0:
            raise argparse.ArgumentTypeError("channel frequencies must be positive")
        if frequency not in seen:
            channels.append(frequency)
            seen.add(frequency)

    if not channels:
        raise argparse.ArgumentTypeError("--channels produced an empty list")

    return channels


def normalise_gateway_distribution(raw: dict) -> dict[str, float]:
    """Return the gateway distribution with normalised keys and float values."""

    distribution: dict[str, float] = {}
    for key, value in raw.items():
        gateway_key = str(key)
        distribution[gateway_key] = float(value)
    return distribution


def aggregate_gateway_distribution(rows: list[dict[str, object]]) -> dict[str, float]:
    """Aggregate gateway distributions across replicates."""

    totals: dict[str, float] = {}
    count = 0
    for row in rows:
        distribution = row.get("pdr_by_gateway_raw")
        if isinstance(distribution, dict) and distribution:
            count += 1
            for key, value in distribution.items():
                totals[key] = totals.get(key, 0.0) + float(value)
    if count == 0:
        return {}
    return {key: totals[key] / count for key in sorted(totals)}


def summarise_replicates(rows: list[dict[str, object]]) -> dict[str, object]:
    """Return aggregated statistics computed from replicate rows."""

    summary: dict[str, object] = {}
    metrics = [
        ("pdr", "pdr_mean", "pdr_std"),
        ("collision_rate", "collision_rate_mean", "collision_rate_std"),
        ("avg_downlink_delay_s", "avg_downlink_delay_s_mean", "avg_downlink_delay_s_std"),
    ]

    for metric_key, mean_key, std_key in metrics:
        values = [
            float(row[metric_key])
            for row in rows
            if isinstance(row.get(metric_key), (int, float))
        ]
        if values:
            summary[mean_key] = statistics.mean(values)
            summary[std_key] = statistics.pstdev(values) if len(values) > 1 else 0.0
        else:
            summary[mean_key] = ""
            summary[std_key] = ""

    distribution = aggregate_gateway_distribution(rows)
    summary["pdr_by_gateway_mean"] = json.dumps(distribution, sort_keys=True)
    return summary


class DownlinkDelayTracker:
    """Context manager recording downlink delays from a scheduler instance."""

    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.delays: list[float] = []
        self._scheduled: dict[int, float] = {}
        self._schedule_func = getattr(scheduler.schedule, "__func__", None)
        self._pop_ready_func = getattr(scheduler.pop_ready, "__func__", None)

    def __enter__(self) -> "DownlinkDelayTracker":
        if self._schedule_func is None or self._pop_ready_func is None:
            return self

        scheduler = self.scheduler
        scheduled = self._scheduled
        delays = self.delays
        schedule_func = self._schedule_func
        pop_ready_func = self._pop_ready_func

        def schedule_wrapper(this, node_id, time, frame, gateway, *args, **kwargs):
            scheduled[id(frame)] = time
            return schedule_func(this, node_id, time, frame, gateway, *args, **kwargs)

        def pop_ready_wrapper(this, node_id, current_time, *args, **kwargs):
            frame, gw = pop_ready_func(this, node_id, current_time, *args, **kwargs)
            if frame is not None:
                scheduled_time = scheduled.pop(id(frame), None)
                if scheduled_time is not None:
                    delay = max(current_time, scheduled_time) - scheduled_time
                    if delay >= 0:
                        delays.append(delay)
            return frame, gw

        scheduler.schedule = types.MethodType(schedule_wrapper, scheduler)  # type: ignore[assignment]
        scheduler.pop_ready = types.MethodType(pop_ready_wrapper, scheduler)  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._schedule_func is None or self._pop_ready_func is None:
            return
        self.scheduler.schedule = types.MethodType(self._schedule_func, self.scheduler)  # type: ignore[assignment]
        self.scheduler.pop_ready = types.MethodType(self._pop_ready_func, self.scheduler)  # type: ignore[assignment]


def main() -> None:  # noqa: D401 - CLI entry point
    parser = argparse.ArgumentParser(
        description=(
            "Run a mobility gateway sweep for RandomWaypoint and SmoothMobility models"
        ),
    )
    parser.add_argument(
        "--gateways-list",
        action="append",
        help=(
            "Comma separated list of gateway counts. Can be repeated. "
            "Defaults to 1,2,4 when omitted."
        ),
    )
    parser.add_argument(
        "--channels",
        action="append",
        help=(
            "Comma separated list of channel frequencies in Hz. Can be repeated. "
            "Defaults to 868.1/868.3/868.5 MHz when omitted."
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

    gateway_values = parse_gateways_list(args.gateways_list)
    channel_plan = parse_channel_frequencies(args.channels)
    area_size = args.range_km * 2000.0

    models = [
        ("random_waypoint", RandomWaypoint),
        ("smooth", SmoothMobility),
    ]

    results: list[dict[str, object]] = []
    combination_index = 0

    for num_gateways in gateway_values:
        for model_name, model_factory in models:
            replicate_rows: list[dict[str, object]] = []

            for replicate in range(1, args.replicates + 1):
                seed = args.seed + combination_index * args.replicates + replicate - 1
                mobility_model = model_factory(area_size)
                sim = Simulator(
                    num_nodes=args.nodes,
                    num_gateways=num_gateways,
                    packets_to_send=args.packets,
                    seed=seed,
                    mobility=True,
                    mobility_model=mobility_model,
                    area_size=area_size,
                    packet_interval=args.interval,
                    adr_node=args.adr_node,
                    adr_server=args.adr_server,
                    channels=MultiChannel(channel_plan),
                )

                with DownlinkDelayTracker(sim.network_server.scheduler) as tracker:
                    sim.run()

                metrics = sim.get_metrics()

                delivered = int(metrics.get("delivered", 0))
                collisions = int(metrics.get("collisions", 0))
                total_packets = delivered + collisions
                collision_rate = collisions / total_packets if total_packets else 0.0

                pdr_by_gateway = normalise_gateway_distribution(
                    metrics.get("pdr_by_gateway", {})
                )

                downlink_samples = len(tracker.delays)
                avg_downlink_delay = (
                    statistics.mean(tracker.delays) if tracker.delays else None
                )

                row = {
                    "model": model_name,
                    "gateways": num_gateways,
                    "range_km": args.range_km,
                    "area_size_m": area_size,
                    "nodes": args.nodes,
                    "channels": json.dumps(channel_plan),
                    "replicate": replicate,
                    "seed": seed,
                    "pdr": float(metrics.get("PDR", 0.0)),
                    "collision_rate": collision_rate,
                    "avg_downlink_delay_s": avg_downlink_delay if avg_downlink_delay is not None else "",
                    "downlink_samples": downlink_samples,
                    "pdr_by_gateway": json.dumps(pdr_by_gateway, sort_keys=True),
                    "pdr_by_gateway_raw": pdr_by_gateway,
                }
                replicate_rows.append(row)

            combination_index += 1

            results.extend(
                {
                    key: value
                    for key, value in row.items()
                    if key != "pdr_by_gateway_raw"
                }
                for row in replicate_rows
            )

            summary = summarise_replicates(replicate_rows)
            summary_row: dict[str, object] = {
                "model": model_name,
                "gateways": num_gateways,
                "range_km": args.range_km,
                "area_size_m": area_size,
                "nodes": args.nodes,
                "channels": json.dumps(channel_plan),
                "replicate": "aggregate",
                "seed": "",
                "pdr": "",
                "collision_rate": "",
                "avg_downlink_delay_s": "",
                "downlink_samples": "",
                "pdr_by_gateway": summary.get("pdr_by_gateway_mean", "{}"),
            }
            for key in ("pdr_mean", "pdr_std", "collision_rate_mean", "collision_rate_std",
                        "avg_downlink_delay_s_mean", "avg_downlink_delay_s_std", "pdr_by_gateway_mean"):
                if key in summary:
                    summary_row[key] = summary[key]
            results.append(summary_row)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"Results saved to {RESULTS_PATH}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
