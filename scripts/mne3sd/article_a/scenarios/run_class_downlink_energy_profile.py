"""Simulate downlink energy usage for LoRaWAN classes B and C.

This scenario focuses on the energy profile of nodes when periodic
downlink traffic is scheduled for classes B and C.  For every replicate
the script runs the :class:`loraflexsim.launcher.simulator.Simulator`
with the requested configuration, records detailed energy metrics and
persists them to ``results/mne3sd/article_a/class_downlink_energy.csv``.

Example usage::

    python -m scripts.mne3sd.article_a.scenarios.run_class_downlink_energy_profile \
        --runs 5 --duration 3600 --nodes 100 --packet-interval 300 \
        --downlink-period 600 --beacon-interval 128 --class-c-rx-interval 1.0
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Allow running the script from a clone without installation
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")),
)

from loraflexsim.launcher import Simulator  # noqa: E402


LOGGER = logging.getLogger("class_downlink_energy")
ROOT = Path(__file__).resolve().parents[4]
RESULTS_PATH = (
    ROOT / "results" / "mne3sd" / "article_a" / "class_downlink_energy.csv"
)

FIELDNAMES = [
    "class",
    "replicate",
    "seed",
    "nodes",
    "gateways",
    "duration_s",
    "packet_interval_s",
    "beacon_interval_s",
    "class_c_rx_interval_s",
    "downlink_period_s",
    "downlink_payload_bytes",
    "uplink_pdr",
    "downlink_pdr",
    "downlink_attempted",
    "downlink_delivered",
    "energy_tx_J",
    "energy_rx_J",
    "energy_idle_J",
    "time_tx_s",
    "time_rx_s",
    "time_idle_s",
]


def positive_int(value: str) -> int:
    """Return ``value`` converted to a strictly positive integer."""

    try:
        parsed = int(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def positive_float(value: str) -> float:
    """Return ``value`` converted to a strictly positive float."""

    try:
        parsed = float(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if parsed <= 0.0:
        raise argparse.ArgumentTypeError("value must be a positive number")
    return parsed


def non_negative_float(value: str) -> float:
    """Return ``value`` converted to a non-negative float."""

    try:
        parsed = float(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if parsed < 0.0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def configure_logging(verbose: bool) -> None:
    """Configure logging with optional debug verbosity."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def _duration_from_energy(energy_j: float, current_a: float, voltage_v: float) -> float:
    """Return the time (s) spent given ``energy_j`` and electrical parameters."""

    if energy_j <= 0.0 or current_a <= 0.0 or voltage_v <= 0.0:
        return 0.0
    return energy_j / (current_a * voltage_v)


def track_downlinks(sim: Simulator) -> None:
    """Augment ``sim`` in-place to track scheduled and delivered downlinks."""

    server = sim.network_server
    server.downlink_scheduled = 0  # type: ignore[attr-defined]
    server.downlink_delivered = 0  # type: ignore[attr-defined]
    original_send = server.send_downlink

    def send_downlink_wrapper(*args, **kwargs):
        server.downlink_scheduled += 1  # type: ignore[attr-defined]
        return original_send(*args, **kwargs)

    server.send_downlink = send_downlink_wrapper  # type: ignore[assignment]

    for node in sim.nodes:
        original_handle = node.handle_downlink

        def handler(frame, *, _original=original_handle, _server=server):
            _server.downlink_delivered += 1  # type: ignore[attr-defined]
            return _original(frame)

        node.handle_downlink = handler  # type: ignore[assignment]


def schedule_downlinks(
    sim: Simulator,
    *,
    period_s: float,
    duration_s: float,
    payload_size: int,
) -> None:
    """Schedule synthetic downlink frames for all nodes every ``period_s``."""

    if period_s <= 0.0:
        return
    payload = bytes(max(payload_size, 0))
    server = sim.network_server
    gateway = sim.gateways[0] if sim.gateways else None
    if gateway is None:  # pragma: no cover - simulator always provides one
        return
    time = period_s
    while time <= duration_s:
        for node in sim.nodes:
            server.send_downlink(node, payload, at_time=time, gateway=gateway)
        time += period_s


def run_for_duration(sim: Simulator, duration: float) -> None:
    """Advance ``sim`` until ``duration`` seconds have elapsed."""

    if duration <= 0.0:
        return
    while sim.event_queue and sim.running:
        next_time = getattr(sim.event_queue[0], "time", None)
        if next_time is not None and next_time > duration:
            break
        sim.step()
    for node in sim.nodes:
        try:
            node.consume_until(duration)
        except AttributeError:  # pragma: no cover - safeguard for legacy nodes
            continue
    sim.current_time = max(sim.current_time, duration)
    sim.stop()


def compute_energy_metrics(
    sim: Simulator,
    metrics: dict[str, Any],
    duration: float,
) -> tuple[float, float, float, float, float, float]:
    """Return aggregate energy (J) and time (s) statistics for ``sim`` nodes."""

    breakdown_by_node: dict[int, dict[str, float]] = metrics.get(
        "energy_breakdown_by_node", {}
    )
    airtime_by_node: dict[int, float] = metrics.get("airtime_by_node", {})

    energy_tx = 0.0
    energy_rx = 0.0
    energy_idle = 0.0
    time_tx = 0.0
    time_rx = 0.0
    time_idle = 0.0

    for node in sim.nodes:
        breakdown = breakdown_by_node.get(node.id, {})
        voltage = getattr(node.profile, "voltage_v", 3.3)
        tx_components = (
            breakdown.get("tx", 0.0)
            + breakdown.get("preamble", 0.0)
            + breakdown.get("startup", 0.0)
            + breakdown.get("ramp", 0.0)
        )
        rx_components = breakdown.get("rx", 0.0) + breakdown.get("listen", 0.0)
        total_energy = sum(breakdown.values())
        idle_components = max(total_energy - tx_components - rx_components, 0.0)

        energy_tx += tx_components
        energy_rx += rx_components
        energy_idle += idle_components

        node_tx_time = airtime_by_node.get(node.id, 0.0)
        node_rx_time = _duration_from_energy(
            breakdown.get("rx", 0.0), getattr(node.profile, "rx_current_a", 0.0), voltage
        )
        node_rx_time += _duration_from_energy(
            breakdown.get("listen", 0.0),
            getattr(node.profile, "listen_current_a", 0.0),
            voltage,
        )

        time_tx += node_tx_time
        time_rx += node_rx_time
        node_idle_time = max(duration - node_tx_time - node_rx_time, 0.0)
        time_idle += node_idle_time

    return energy_tx, energy_rx, energy_idle, time_tx, time_rx, time_idle


def aggregate_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return mean and standard deviation rows grouped by class."""

    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["class"])].append(row)

    summaries: list[dict[str, Any]] = []
    metrics = [
        "uplink_pdr",
        "downlink_pdr",
        "downlink_attempted",
        "downlink_delivered",
        "energy_tx_J",
        "energy_rx_J",
        "energy_idle_J",
        "time_tx_s",
        "time_rx_s",
        "time_idle_s",
    ]

    for class_type, entries in grouped.items():
        if not entries:
            continue
        summary_base = {
            "class": class_type,
            "seed": "",
            "nodes": entries[0]["nodes"],
            "gateways": entries[0]["gateways"],
            "duration_s": entries[0]["duration_s"],
            "packet_interval_s": entries[0]["packet_interval_s"],
            "beacon_interval_s": entries[0]["beacon_interval_s"],
            "class_c_rx_interval_s": entries[0]["class_c_rx_interval_s"],
            "downlink_period_s": entries[0]["downlink_period_s"],
            "downlink_payload_bytes": entries[0]["downlink_payload_bytes"],
        }

        mean_row = {"replicate": "mean", **summary_base}
        std_row = {"replicate": "std", **summary_base}

        for metric in metrics:
            values = [float(entry[metric]) for entry in entries]
            mean_row[metric] = statistics.fmean(values)
            std_row[metric] = statistics.pstdev(values) if len(values) > 1 else 0.0
        summaries.extend([mean_row, std_row])
    return summaries


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Return parsed command line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Simulate energy consumption for LoRaWAN classes B and C under "
            "periodic downlink traffic."
        )
    )
    parser.add_argument("--config", help="Optional simulator INI configuration file")
    parser.add_argument("--seed", type=int, default=1, help="Base random seed")
    parser.add_argument(
        "--runs",
        type=positive_int,
        default=5,
        help="Number of Monte Carlo replicates (must be at least 5)",
    )
    parser.add_argument(
        "--duration",
        type=positive_float,
        default=3600.0,
        help="Simulation duration in seconds",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_PATH),
        help="Target CSV file for the collected metrics",
    )
    parser.add_argument(
        "--nodes",
        type=positive_int,
        default=100,
        help="Number of end devices to simulate",
    )
    parser.add_argument(
        "--gateways",
        type=positive_int,
        default=1,
        help="Number of gateways",
    )
    parser.add_argument(
        "--packet-interval",
        type=positive_float,
        default=300.0,
        help="Mean uplink packet interval per node in seconds",
    )
    parser.add_argument(
        "--payload-size",
        type=positive_int,
        default=20,
        help="Uplink payload size in bytes",
    )
    parser.add_argument(
        "--mode",
        choices=["random", "periodic"],
        default="random",
        help="Uplink traffic mode",
    )
    parser.add_argument(
        "--adr-node",
        action="store_true",
        help="Enable ADR on the nodes",
    )
    parser.add_argument(
        "--adr-server",
        action="store_true",
        help="Enable ADR on the network server",
    )
    parser.add_argument(
        "--duty-cycle",
        type=non_negative_float,
        default=0.01,
        help="Duty cycle constraint (fraction, 0 disables)",
    )
    parser.add_argument(
        "--mobility",
        action="store_true",
        help="Enable node mobility",
    )
    parser.add_argument(
        "--downlink-period",
        type=positive_float,
        default=600.0,
        help="Synthetic downlink period applied to all nodes (seconds)",
    )
    parser.add_argument(
        "--downlink-payload",
        type=positive_int,
        default=8,
        help="Downlink payload size in bytes",
    )
    parser.add_argument(
        "--beacon-interval",
        type=positive_float,
        default=128.0,
        help="Beacon interval for class B scheduling (seconds)",
    )
    parser.add_argument(
        "--class-c-rx-interval",
        type=positive_float,
        default=1.0,
        help="Polling interval for Class C receive windows (seconds)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args(argv)
    if args.runs < 5:
        parser.error("--runs must be at least 5 to ensure statistical confidence")
    return args


def main(argv: list[str] | None = None) -> None:  # noqa: D401 - CLI entry point
    args = parse_args(argv)
    configure_logging(args.verbose)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    classes = ["B", "C"]
    rows: list[dict[str, Any]] = []

    for class_index, class_type in enumerate(classes):
        LOGGER.info("=== Simulating class %s ===", class_type)
        for replicate in range(1, args.runs + 1):
            seed_offset = class_index * args.runs + (replicate - 1)
            seed = args.seed + seed_offset
            LOGGER.info("Replicate %d/%d (seed=%d)", replicate, args.runs, seed)

            simulator_kwargs: dict[str, Any] = {
                "num_nodes": args.nodes,
                "num_gateways": args.gateways,
                "packet_interval": args.packet_interval,
                "packets_to_send": 0,
                "payload_size_bytes": args.payload_size,
                "node_class": class_type,
                "seed": seed,
                "class_c_rx_interval": args.class_c_rx_interval,
                "adr_node": args.adr_node,
                "adr_server": args.adr_server,
                "duty_cycle": None if args.duty_cycle == 0 else args.duty_cycle,
                "mobility": args.mobility,
            }
            if args.mode == "periodic":
                simulator_kwargs["transmission_mode"] = "Periodic"
            else:
                simulator_kwargs["transmission_mode"] = "Random"
            if args.config:
                simulator_kwargs["config_file"] = args.config

            sim = Simulator(**simulator_kwargs)

            # Align beacon configuration and track downlink metrics
            sim.beacon_interval = args.beacon_interval
            sim.network_server.beacon_interval = args.beacon_interval
            track_downlinks(sim)

            schedule_downlinks(
                sim,
                period_s=args.downlink_period,
                duration_s=args.duration,
                payload_size=args.downlink_payload,
            )

            run_for_duration(sim, args.duration)
            metrics = sim.get_metrics()

            (
                energy_tx,
                energy_rx,
                energy_idle,
                time_tx,
                time_rx,
                time_idle,
            ) = compute_energy_metrics(sim, metrics, args.duration)

            downlink_attempted = getattr(sim.network_server, "downlink_scheduled", 0)
            downlink_delivered = getattr(sim.network_server, "downlink_delivered", 0)
            downlink_pdr = (
                downlink_delivered / downlink_attempted
                if downlink_attempted
                else 0.0
            )

            row: dict[str, Any] = {
                "class": class_type,
                "replicate": replicate,
                "seed": seed,
                "nodes": args.nodes,
                "gateways": args.gateways,
                "duration_s": args.duration,
                "packet_interval_s": args.packet_interval,
                "beacon_interval_s": args.beacon_interval,
                "class_c_rx_interval_s": args.class_c_rx_interval,
                "downlink_period_s": args.downlink_period,
                "downlink_payload_bytes": args.downlink_payload,
                "uplink_pdr": float(metrics.get("PDR", 0.0)),
                "downlink_pdr": downlink_pdr,
                "downlink_attempted": downlink_attempted,
                "downlink_delivered": downlink_delivered,
                "energy_tx_J": energy_tx,
                "energy_rx_J": energy_rx,
                "energy_idle_J": energy_idle,
                "time_tx_s": time_tx,
                "time_rx_s": time_rx,
                "time_idle_s": time_idle,
            }
            rows.append(row)

    summary_rows = aggregate_summary(rows)
    all_rows = rows + summary_rows

    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})

    LOGGER.info("Saved %s", output_path)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
