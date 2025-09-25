"""Utility helpers for simulation analysis scripts.

This module centralises filesystem helpers and statistical utilities
used by multiple scenario automation scripts.  It keeps the scripts
lightweight while ensuring consistent computation of latency and energy
statistics.
"""

from __future__ import annotations

import math
import os
from typing import Iterable, Sequence

import numpy as np

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "figures")


def ensure_directory(path: str) -> None:
    """Create *path* if it does not already exist."""

    os.makedirs(path, exist_ok=True)


def ensure_output_directories() -> None:
    """Create the standard ``results`` and ``figures`` folders."""

    ensure_directory(RESULTS_DIR)
    ensure_directory(FIGURES_DIR)


def collect_latencies(
    events: Sequence[dict],
    node_ids: Iterable[int] | None = None,
) -> list[float]:
    """Return transmission delays for successful packets.

    Parameters
    ----------
    events:
        Sequence of event dictionaries produced by ``Simulator``.
    node_ids:
        Optional iterable restricting the collection to specific nodes.
    """

    node_filter = set(node_ids) if node_ids is not None else None
    latencies: list[float] = []
    for entry in events:
        if entry.get("result") != "Success":
            continue
        if node_filter is not None and entry.get("node_id") not in node_filter:
            continue
        start = float(entry.get("start_time", 0.0))
        end = float(entry.get("end_time", start))
        latencies.append(end - start)
    return latencies


def summarise_nodes(
    nodes: Sequence[object],
    node_ids: Iterable[int] | None = None,
) -> tuple[int, int, list[float]]:
    """Return attempts, deliveries and per-node energy for the subset."""

    node_filter = set(node_ids) if node_ids is not None else None
    attempts = 0
    deliveries = 0
    energies: list[float] = []
    for node in nodes:
        if node_filter is not None and getattr(node, "id", None) not in node_filter:
            continue
        attempts += int(getattr(node, "tx_attempted", 0))
        deliveries += int(getattr(node, "rx_delivered", 0))
        energies.append(float(getattr(node, "energy_consumed", 0.0)))
    return attempts, deliveries, energies


def compute_latency_stats(latencies: Sequence[float]) -> dict[str, float]:
    """Compute mean and 95th percentile latency."""

    if not latencies:
        return {"mean": 0.0, "p95": 0.0}
    arr = np.asarray(latencies, dtype=float)
    return {
        "mean": float(arr.mean()),
        "p95": float(np.percentile(arr, 95)),
    }


def place_gateways_in_grid(gateways: Sequence[object], area_size: float) -> None:
    """Reposition gateways on a uniform grid covering the area."""

    count = len(gateways)
    if count == 0:
        return
    side = int(math.ceil(math.sqrt(count)))
    spacing = area_size / (side + 1)
    for index, gateway in enumerate(gateways):
        row = index // side
        col = index % side
        setattr(gateway, "x", spacing * (col + 1))
        setattr(gateway, "y", spacing * (row + 1))
