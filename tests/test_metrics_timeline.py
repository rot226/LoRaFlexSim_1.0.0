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
