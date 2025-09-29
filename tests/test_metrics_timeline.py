import pytest

from loraflexsim.launcher.channel import Channel
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


def test_omnet_channel_updates_last_rssi():
    channel = Channel(
        phy_model="omnet",
        shadowing_std=0.0,
        fast_fading_std=0.0,
        tx_power_std=0.0,
        time_variation_std=0.0,
        fine_fading_std=0.0,
        pa_non_linearity_std_dB=0.0,
        phase_noise_std_dB=0.0,
        freq_offset_std_hz=0.0,
        sync_offset_std_s=0.0,
        noise_floor_std=0.0,
        impulsive_noise_prob=0.0,
        variable_noise_std=0.0,
    )
    rssi1, _ = channel.compute_rssi(14.0, 100.0, sf=7)
    assert channel.last_rssi_dBm == pytest.approx(rssi1)

    rssi2, _ = channel.compute_rssi(10.0, 150.0, sf=7)
    assert channel.last_rssi_dBm == pytest.approx(rssi2)
