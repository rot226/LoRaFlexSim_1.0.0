#!/usr/bin/env python3
"""Evaluate packet delivery ratio (PDR) as the network load varies.

This helper runs several LoRaFlexSim configurations covering different traffic
volumes, temporal distributions (periodic vs. random) and spreading-factor
assignments.  The detailed metrics are written to
``results/mne3sd/article_a/pdr_load.csv`` to facilitate post-processing.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from itertools import product
from pathlib import Path
from typing import Iterable

# Allow running the script from a clone without installation
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
)

from loraflexsim.launcher import Simulator  # noqa: E402
from scripts.mne3sd.common import (  # noqa: E402
    add_execution_profile_argument,
    resolve_execution_profile,
    summarise_metrics,
    write_csv,
)


LOGGER = logging.getLogger("simulate_pdr_load")
ROOT = Path(__file__).resolve().parents[4]
RESULTS_DIR = ROOT / "results" / "mne3sd" / "article_a"
DETAIL_CSV = RESULTS_DIR / "pdr_load.csv"
SUMMARY_CSV = RESULTS_DIR / "pdr_load_summary.csv"

DEFAULT_INTERVALS = (900.0, 600.0, 300.0, 120.0, 60.0)
DEFAULT_MODES = ("random", "periodic")
DEFAULT_FIXED_SF: tuple[int | None, ...] = (None, 7, 9, 12)
DEFAULT_REPLICATES = 5

CI_INTERVALS = (600.0,)
CI_MODES = ("random",)
CI_REPLICATES = 1


def positive_int(value: str) -> int:
    """Return ``value`` converted to a strictly positive integer."""

    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return ivalue


def positive_float(value: str) -> float:
    """Return ``value`` converted to a strictly positive float."""

    fvalue = float(value)
    if fvalue <= 0:
        raise argparse.ArgumentTypeError("value must be a positive float")
    return fvalue


def parse_intervals(values: Iterable[float] | None) -> list[float]:
    """Normalise interval values into a sorted, de-duplicated list."""

    candidates = DEFAULT_INTERVALS if not values else tuple(float(v) for v in values)
    ordered: list[float] = []
    seen: set[float] = set()
    for interval in candidates:
        if interval not in seen:
            ordered.append(interval)
            seen.add(interval)
    ordered.sort(reverse=True)
    return ordered


def parse_modes(values: Iterable[str] | None) -> list[str]:
    """Normalise the requested transmission modes."""

    if not values:
        return list(DEFAULT_MODES)
    modes: list[str] = []
    for mode in values:
        candidate = mode.strip().lower()
        if candidate not in {"random", "periodic"}:
            raise argparse.ArgumentTypeError(
                f"unsupported mode '{mode}', expected 'random' or 'periodic'"
            )
        if candidate not in modes:
            modes.append(candidate)
    return modes


def parse_spreading_factors(values: Iterable[str] | None) -> list[int | None]:
    """Return a list of SF assignments (``None`` triggers ADR)."""

    if not values:
        return list(DEFAULT_FIXED_SF)
    parsed: list[int | None] = []
    for value in values:
        cleaned = value.strip().lower()
        if cleaned in {"", "adr", "adaptive"}:
            if None not in parsed:
                parsed.append(None)
            continue
        sf = int(cleaned)
        if sf < 7 or sf > 12:
            raise argparse.ArgumentTypeError(
                f"invalid spreading factor '{value}', expected 7–12 or 'adr'"
            )
        if sf not in parsed:
            parsed.append(sf)
    return parsed


def configure_logging(verbose: bool) -> None:
    """Initialise logging depending on verbosity preference."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def main() -> None:  # noqa: D401 - CLI entry point
    parser = argparse.ArgumentParser(
        description="Simulate PDR as a function of traffic load"
    )
    parser.add_argument("--nodes", type=positive_int, default=100, help="Number of nodes")
    parser.add_argument(
        "--packets",
        type=positive_int,
        default=20,
        help="Packets transmitted per node",
    )
    parser.add_argument(
        "--interval",
        action="append",
        type=positive_float,
        help="Mean packet interval in seconds (may be repeated)",
    )
    parser.add_argument(
        "--mode",
        action="append",
        help="Traffic mode: 'random' (Poisson) or 'periodic'. May be repeated.",
    )
    parser.add_argument(
        "--fixed-sf",
        action="append",
        help=(
            "Spreading factor assignment. Use numeric values (7–12) or 'ADR' for "
            "adaptive data rate. May be repeated."
        ),
    )
    parser.add_argument(
        "--replicates",
        type=positive_int,
        default=DEFAULT_REPLICATES,
        help="Number of replicates per configuration",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Base random seed used for the first replicate",
    )
    parser.add_argument(
        "--adr-node",
        action="store_true",
        help="Enable ADR on the nodes when no fixed SF is provided",
    )
    parser.add_argument(
        "--adr-server",
        action="store_true",
        help="Enable ADR on the network server when no fixed SF is provided",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    add_execution_profile_argument(parser)
    args = parser.parse_args()

    configure_logging(args.verbose)

    profile = resolve_execution_profile(args.profile)
    intervals = parse_intervals(args.interval)
    modes = parse_modes(args.mode)
    sf_values = parse_spreading_factors(args.fixed_sf)

    nodes = args.nodes
    packets = args.packets
    replicates = args.replicates
    adr_node = args.adr_node
    adr_server = args.adr_server
    if profile == "ci":
        intervals = list(CI_INTERVALS)
        modes = list(CI_MODES)
        replicates = min(replicates, CI_REPLICATES)
        nodes = min(nodes, 30)
        packets = min(packets, 10)

    LOGGER.info(
        "Simulating PDR for %d nodes with intervals %s and modes %s",
        nodes,
        ", ".join(f"{i:.0f}s" for i in intervals),
        ", ".join(modes),
    )

    results: list[dict[str, object]] = []
    summary_inputs: list[dict[str, object]] = []

    seed_counter = args.seed
    for interval_s, mode, sf_value in product(intervals, modes, sf_values):
        config_label = "ADR" if sf_value is None else f"SF{sf_value}"
        LOGGER.info("Interval %.1fs, mode %s, %s", interval_s, mode, config_label)

        for replicate in range(1, replicates + 1):
            sim = Simulator(
                num_nodes=nodes,
                packets_to_send=packets,
                packet_interval=interval_s,
                transmission_mode=mode.capitalize(),
                fixed_sf=sf_value,
                adr_node=adr_node if sf_value is None else False,
                adr_server=adr_server if sf_value is None else False,
                seed=seed_counter,
            )
            seed_counter += 1
            sim.run()
            metrics = sim.get_metrics()

            energy_nodes = float(metrics.get("energy_nodes_J", 0.0))
            delivered = int(metrics.get("delivered", 0))
            collisions = int(metrics.get("collisions", 0))
            pdr = float(metrics.get("PDR", 0.0))
            avg_delay = float(metrics.get("avg_delay_s", 0.0))
            throughput = float(metrics.get("throughput_bps", 0.0))
            pdr_by_sf = metrics.get("pdr_by_sf", {})
            pdr_by_class = metrics.get("pdr_by_class", {})
            energy_per_node = energy_nodes / nodes if nodes else 0.0
            offered_pps = nodes / interval_s

            row = {
                "nodes": nodes,
                "packets": packets,
                "interval_s": interval_s,
                "mode": mode,
                "sf_assignment": config_label,
                "replicate": replicate,
                "seed": seed_counter - 1,
                "adr_node": int(adr_node if sf_value is None else False),
                "adr_server": int(adr_server if sf_value is None else False),
                "offered_load_pps": offered_pps,
                "pdr": pdr,
                "delivered": delivered,
                "collisions": collisions,
                "avg_delay_s": avg_delay,
                "throughput_bps": throughput,
                "energy_per_node_J": energy_per_node,
            }

            for sf in range(7, 13):
                row[f"pdr_sf{sf}"] = float(pdr_by_sf.get(sf, 0.0))

            for class_type, class_pdr in pdr_by_class.items():
                row[f"pdr_class_{class_type}"] = float(class_pdr)

            results.append(row)
            summary_inputs.append(row)

            LOGGER.debug(
                "Replicate %d -> PDR %.3f, collisions %d, throughput %.2f bps",
                replicate,
                pdr,
                collisions,
                throughput,
            )

    if not results:
        LOGGER.warning("No simulations executed; skipping CSV generation")
        return

    fieldnames = [
        "nodes",
        "packets",
        "interval_s",
        "mode",
        "sf_assignment",
        "replicate",
        "seed",
        "adr_node",
        "adr_server",
        "offered_load_pps",
        "pdr",
        "delivered",
        "collisions",
        "avg_delay_s",
        "throughput_bps",
        "energy_per_node_J",
    ]
    fieldnames.extend([f"pdr_sf{sf}" for sf in range(7, 13)])
    class_columns = sorted(
        {key for row in results for key in row if key.startswith("pdr_class_")}
    )
    fieldnames.extend(class_columns)

    write_csv(DETAIL_CSV, fieldnames, results)

    summary_rows = summarise_metrics(
        summary_inputs,
        ["interval_s", "mode", "sf_assignment", "adr_node", "adr_server"],
        [
            "pdr",
            "avg_delay_s",
            "collisions",
            "throughput_bps",
            "energy_per_node_J",
            "pdr_sf7",
            "pdr_sf8",
            "pdr_sf9",
            "pdr_sf10",
            "pdr_sf11",
            "pdr_sf12",
        ],
    )
    summary_fieldnames = list(summary_rows[0].keys()) if summary_rows else []
    if summary_fieldnames:
        write_csv(SUMMARY_CSV, summary_fieldnames, summary_rows)
        LOGGER.info("Saved %s and %s", DETAIL_CSV, SUMMARY_CSV)
    else:
        LOGGER.info("Saved %s", DETAIL_CSV)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
