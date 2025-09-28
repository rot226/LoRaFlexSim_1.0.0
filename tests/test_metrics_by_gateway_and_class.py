"""Tests des métriques par passerelle et par classe."""

from __future__ import annotations

import heapq

import pytest

from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher.simulator import EventType, Simulator


def _schedule_transmissions(sim: Simulator, schedule: dict[int, float]) -> None:
    """Reprogramme les transmissions initiales selon ``schedule``."""
    for event in sim.event_queue:
        if event.type != EventType.TX_START:
            continue
        node_id = event.node_id
        if node_id not in schedule:
            continue
        time = schedule[node_id]
        event.time = sim._seconds_to_ticks(time)
        node = sim.node_map[node_id]
        if node.interval_log:
            node.interval_log[-1]["tx_time"] = time
    heapq.heapify(sim.event_queue)


def _collect_gateway_deliveries(sim: Simulator) -> dict[int, int]:
    """Compte les paquets livrés par passerelle via le serveur réseau."""
    delivered = {gw.id: 0 for gw in sim.gateways}
    for gw_id in sim.network_server.event_gateway.values():
        delivered[gw_id] = delivered.get(gw_id, 0) + 1
    return delivered


def _assert_energy_metrics(metrics: dict, gateway_ids: set[int], classes: set[str]) -> None:
    """Valide la présence et la cohérence des métriques d'énergie."""
    for cls in classes:
        key = f"energy_class_{cls}_J"
        assert key in metrics
        assert metrics[key] >= 0.0
    energy_by_gateway = metrics["energy_by_gateway"]
    assert set(energy_by_gateway) == gateway_ids
    for value in energy_by_gateway.values():
        assert value >= 0.0


def test_metrics_per_gateway_and_class_success() -> None:
    """Chaque passerelle doit recevoir une transmission réussie."""
    sim = Simulator(
        num_nodes=2,
        num_gateways=2,
        area_size=1000.0,
        packets_to_send=1,
        mobility=False,
        seed=1,
        channels=[Channel(frequency_hz=868_100_000.0)],
        fixed_sf=7,
    )

    # Positionner chaque nœud près d'une passerelle distincte
    gw_left, gw_right = sim.gateways
    gw_left.x = 0.0
    gw_left.y = 0.0
    gw_right.x = 1000.0
    gw_right.y = 0.0

    node_left, node_right = sim.nodes
    node_left.x = node_left.initial_x = 0.1
    node_left.y = node_left.initial_y = 0.0
    node_left.class_type = "A"

    node_right.x = node_right.initial_x = 999.9
    node_right.y = node_right.initial_y = 0.0
    node_right.class_type = "C"
    sim.ensure_class_c_rx_window(node_right)

    _schedule_transmissions(sim, {node_left.id: 1.0, node_right.id: 2.0})

    sim.run()
    metrics = sim.get_metrics()

    attempts = sim.tx_attempted
    assert attempts == 2
    gateway_ids = {gw.id for gw in sim.gateways}
    assert set(metrics["pdr_by_gateway"]) == gateway_ids

    delivered_by_gateway = _collect_gateway_deliveries(sim)
    for gw_id, count in delivered_by_gateway.items():
        expected = count / attempts
        assert metrics["pdr_by_gateway"][gw_id] == pytest.approx(expected)

    classes = {node.class_type for node in sim.nodes}
    assert set(metrics["pdr_by_class"]) == classes
    for cls in classes:
        cls_nodes = [n for n in sim.nodes if n.class_type == cls]
        sent = sum(n.tx_attempted for n in cls_nodes)
        delivered = sum(n.rx_delivered for n in cls_nodes)
        expected = delivered / sent if sent else 0.0
        assert metrics["pdr_by_class"][cls] == pytest.approx(expected)

    _assert_energy_metrics(metrics, gateway_ids, classes)


def test_metrics_per_gateway_and_class_with_collision() -> None:
    """Une collision doit modifier les ratios : seule une passerelle livre."""
    sim = Simulator(
        num_nodes=2,
        num_gateways=2,
        area_size=1000.0,
        packets_to_send=1,
        mobility=False,
        seed=2,
        channels=[Channel(frequency_hz=868_100_000.0)],
        fixed_sf=7,
    )

    gw_left, gw_right = sim.gateways
    gw_left.x = 0.0
    gw_left.y = 0.0
    gw_right.x = 1000.0
    gw_right.y = 0.0

    strong, weak = sim.nodes
    strong.x = strong.initial_x = 0.1
    strong.y = strong.initial_y = 0.0
    strong.tx_power = strong.initial_tx_power = 14.0
    strong.class_type = "A"

    weak.x = weak.initial_x = 0.2
    weak.y = weak.initial_y = 0.0
    weak.tx_power = weak.initial_tx_power = 2.0
    weak.class_type = "C"
    sim.ensure_class_c_rx_window(weak)

    symbol_duration = (2 ** strong.sf) / strong.channel.bandwidth
    start_strong = 1.0
    start_weak = start_strong + symbol_duration * 6.0

    _schedule_transmissions(sim, {strong.id: start_strong, weak.id: start_weak})

    sim.run()
    metrics = sim.get_metrics()

    attempts = sim.tx_attempted
    assert attempts == 2
    assert metrics["collisions"] == 1
    gateway_ids = {gw.id for gw in sim.gateways}
    delivered_by_gateway = _collect_gateway_deliveries(sim)

    for gw in sim.gateways:
        expected = delivered_by_gateway[gw.id] / attempts
        assert metrics["pdr_by_gateway"][gw.id] == pytest.approx(expected)

    classes = {node.class_type for node in sim.nodes}
    assert metrics["pdr_by_class"]["A"] == pytest.approx(1.0)
    assert metrics["pdr_by_class"]["C"] == pytest.approx(0.0)

    _assert_energy_metrics(metrics, gateway_ids, classes)
