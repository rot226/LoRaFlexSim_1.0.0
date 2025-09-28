"""Tests d'intégration pour la cohérence des métriques par classe."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher.simulator import Simulator


def _make_static_channel() -> Channel:
    """Retourne un canal dépourvu d'aléas pour des scénarios déterministes."""

    return Channel(
        shadowing_std=0.0,
        fast_fading_std=0.0,
        time_variation_std=0.0,
        variable_noise_std=0.0,
        noise_floor_std=0.0,
        multipath_taps=1,
        impulsive_noise_prob=0.0,
        impulsive_noise_dB=0.0,
        phase_noise_std_dB=0.0,
        clock_jitter_std_s=0.0,
        pa_ramp_up_s=0.0,
        pa_ramp_down_s=0.0,
        fine_fading_std=0.0,
    )


def _advance_until(
    sim: Simulator, condition: Callable[[], bool], max_steps: int = 256
) -> None:
    """Fait avancer ``sim`` jusqu'à ce que ``condition`` soit vraie ou la limite atteinte."""

    for _ in range(max_steps):
        if condition():
            return
        progressed = sim.step()
        if not progressed:
            break
    assert condition(), "La condition attendue n'a pas été atteinte dans le budget d'étapes."


@pytest.mark.parametrize("class_type, seed", [("A", 11), ("B", 17), ("C", 23)])
def test_metrics_populated_without_downlink(class_type: str, seed: int) -> None:
    """Les métriques doivent être renseignées pour chaque classe après un premier uplink."""

    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        area_size=1.0,
        transmission_mode="Periodic",
        packet_interval=5.0,
        packets_to_send=1,
        mobility=False,
        channels=[_make_static_channel()],
        node_class=class_type,
        fixed_sf=7,
        fixed_tx_power=14,
        seed=seed,
    )

    _advance_until(sim, lambda: sim.rx_delivered >= 1)

    metrics = sim.get_metrics()
    node_id = sim.nodes[0].id

    assert metrics["tx_attempted"] == 1
    assert metrics["delivered"] == 1
    assert metrics["pdr_by_class"].get(class_type) == pytest.approx(1.0)
    assert metrics["energy_by_class"].get(class_type, 0.0) > 0.0
    assert metrics["pdr_by_node"].get(node_id) == pytest.approx(1.0)
    assert metrics["recent_pdr_by_node"].get(node_id) == pytest.approx(1.0)


def test_metrics_remain_consistent_with_downlink() -> None:
    """Les compteurs doivent rester cohérents lorsqu'un downlink est traité rapidement."""

    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        area_size=1.0,
        transmission_mode="Periodic",
        packet_interval=5.0,
        packets_to_send=1,
        mobility=False,
        channels=[_make_static_channel()],
        node_class="C",
        fixed_sf=7,
        fixed_tx_power=14,
        seed=101,
    )

    node = sim.nodes[0]

    _advance_until(sim, lambda: sim.rx_delivered >= 1)
    baseline = sim.get_metrics()
    initial_fcnt_down = node.fcnt_down

    sim.network_server.send_downlink(node, b"payload")
    sim.ensure_class_c_rx_window(node)
    assert node.downlink_pending >= 1

    _advance_until(sim, lambda: node.downlink_pending == 0)

    metrics = sim.get_metrics()

    assert node.downlink_pending == 0
    assert node.fcnt_down == initial_fcnt_down + 1
    assert metrics["pdr_by_class"].get("C") == pytest.approx(1.0)
    assert metrics["pdr_by_node"].get(node.id) == pytest.approx(1.0)
    assert metrics["recent_pdr_by_node"].get(node.id) == pytest.approx(1.0)
    assert metrics["energy_by_class"]["C"] >= baseline["energy_by_class"]["C"]
    gateway_id = sim.gateways[0].id
    assert metrics["energy_by_gateway"][gateway_id] > 0.0
