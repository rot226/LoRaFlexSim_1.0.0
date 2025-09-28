import pytest

import pytest

from loraflexsim.launcher.simulator import Simulator


def _timeline_records(timeline):
    if hasattr(timeline, "to_dict"):
        try:
            return timeline.to_dict(orient="records")  # type: ignore[call-arg]
        except TypeError:
            # Compatibilité éventuelle avec DataFrame.to_dict("records")
            return timeline.to_dict("records")  # type: ignore[call-arg]
    return [dict(entry) for entry in timeline]


def test_metrics_timeline_matches_tx_end_events():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=3,
        duty_cycle=None,
        seed=123,
    )
    sim.run()

    timeline = sim.get_metrics_timeline()
    records = _timeline_records(timeline)

    assert len(records) == sim.tx_attempted == 3
    assert records[0]["time_s"] >= 0.0

    for idx, entry in enumerate(records, start=1):
        assert entry["tx_attempted"] == idx
        tx = entry["tx_attempted"]
        delivered = entry["delivered"]
        expected_pdr = delivered / tx if tx > 0 else 0.0
        assert entry["PDR"] == pytest.approx(expected_pdr)
        assert entry["collisions"] == 0

    final = records[-1]
    assert final["PDR"] == pytest.approx(sim.rx_delivered / sim.tx_attempted)
    assert final["energy_J"] >= 0.0
    assert "instant_throughput_bps" in final
    assert final["instant_throughput_bps"] >= 0.0
    assert "instant_avg_delay_s" in final
    assert final["instant_avg_delay_s"] >= 0.0
    assert "recent_losses" in final
    assert final["recent_losses"] >= 0.0
    assert "losses_total" in final
    assert final["losses_total"] == pytest.approx(final["tx_attempted"] - final["delivered"])


def test_metrics_timeline_accounts_for_server_delay():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=2.0,
        packets_to_send=1,
        duty_cycle=None,
        flora_mode=True,
        flora_timing=True,
        mobility=False,
        area_size=10.0,
        seed=321,
    )
    if sim.nodes and sim.gateways:
        node = sim.nodes[0]
        gateway = sim.gateways[0]
        node.x = node.y = 0.0
        node.initial_x = node.initial_y = 0.0
        gateway.x = gateway.y = 0.0
    sim.run()

    timeline = sim.get_metrics_timeline()
    records = _timeline_records(timeline)

    assert len(records) == 1
    entry = records[0]
    expected_time = (
        sim.events_log[0]["end_time"]
        + sim.network_server.network_delay
        + sim.network_server.process_delay
    )
    assert entry["time_s"] == pytest.approx(expected_time)
    assert entry["delivered"] == 1
    assert entry["PDR"] == pytest.approx(1.0)
    assert entry["instant_throughput_bps"] > 0.0
    assert entry["instant_avg_delay_s"] > 0.0
