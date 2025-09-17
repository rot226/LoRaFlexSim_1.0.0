"""Integration checks for the large area long range scenario."""

from __future__ import annotations

import math

import pytest

from loraflexsim.launcher import Channel, Simulator
from loraflexsim.scenarios import (
    LONG_RANGE_AREA_SIZE,
    LONG_RANGE_BANDWIDTHS,
    LONG_RANGE_DISTANCES,
    LONG_RANGE_RECOMMENDATIONS,
    LONG_RANGE_SPREADING_FACTORS,
    build_long_range_simulator,
)


@pytest.mark.parametrize(
    "preset",
    ["flora", "flora_hata", "rural_long_range"],
)
def test_long_range_large_area_meets_pdr_and_sensitivity(preset: str) -> None:
    """Ensure the long range scenario preserves coverage at 10–12 km."""

    params = LONG_RANGE_RECOMMENDATIONS[preset]
    simulator = build_long_range_simulator(preset, seed=3, packets_per_node=params.packets_per_node)
    simulator.run()
    metrics = simulator.get_metrics()

    # Area check (square side length squared) expressed in square metres.
    assert pytest.approx(simulator.area_size, rel=1e-6) == LONG_RANGE_AREA_SIZE
    assert simulator.area_size ** 2 >= 10_000_000.0

    gateway = simulator.gateways[0]
    distances = [
        math.hypot(node.x - gateway.x, node.y - gateway.y) for node in simulator.nodes
    ]
    assert any(10_000.0 <= d <= 12_000.0 for d in distances)
    assert distances[0] == pytest.approx(LONG_RANGE_DISTANCES[0])
    assert sorted(node.sf for node in simulator.nodes) == sorted(LONG_RANGE_SPREADING_FACTORS)

    sf12_pdr = metrics["pdr_by_sf"][12]
    assert sf12_pdr >= 0.7

    # Gather all successful receptions to verify the sensitivity margins.
    successful_sf12 = [
        ev
        for ev in simulator.events_log
        if ev.get("result") == "Success" and ev["sf"] == 12 and ev["rssi_dBm"] is not None
    ]
    assert successful_sf12, "No SF12 receptions recorded"

    maxima: dict[int, dict[str, float]] = {}
    for event in successful_sf12:
        node = next(n for n in simulator.nodes if n.id == event["node_id"])
        bandwidth = int(node.channel.bandwidth)
        stats = maxima.setdefault(bandwidth, {"rssi": -float("inf"), "snr": -float("inf")})
        stats["rssi"] = max(stats["rssi"], event["rssi_dBm"])
        stats["snr"] = max(stats["snr"], event["snr_dB"])

    expected_bandwidths = {int(bw) for bw in LONG_RANGE_BANDWIDTHS}
    assert set(maxima) == expected_bandwidths

    for bandwidth, stats in maxima.items():
        sensitivity = Channel.FLORA_SENSITIVITY[12][bandwidth]
        assert stats["rssi"] >= sensitivity - 0.1
        assert stats["snr"] >= Simulator.REQUIRED_SNR[12]
