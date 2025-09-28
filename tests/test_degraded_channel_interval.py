import pytest

from loraflexsim.launcher.adr_standard_1 import apply as apply_adr
from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher.multichannel import MultiChannel
from loraflexsim.launcher.simulator import Simulator


def test_interval_with_flora_channel():
    mean_interval = 2.0
    packets = 1000
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Random",
        packet_interval=mean_interval,
        packets_to_send=packets,
        pure_poisson_mode=True,
        mobility=False,
        seed=1,
    )
    apply_adr(sim)
    sim.run()
    node = sim.nodes[0]
    average = node._last_arrival_time / node.packets_sent
    assert node.packets_sent == packets
    assert abs(average - mean_interval) / mean_interval < 0.02


def test_channels_configured_for_flora_capture():
    channels = [
        Channel(frequency_hz=868.1e6),
        Channel(frequency_hz=868.3e6),
        Channel(frequency_hz=868.5e6),
    ]
    multi = MultiChannel(channels)
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Random",
        packet_interval=1.0,
        packets_to_send=1,
        pure_poisson_mode=True,
        mobility=False,
        channels=multi,
        seed=1,
    )
    apply_adr(sim)

    reference = sim.multichannel.channels[0]
    for ch in sim.multichannel.channels:
        assert ch.orthogonal_sf is False
        assert ch.non_orth_delta == reference.non_orth_delta

    node_channel = sim.nodes[0].channel
    assert node_channel.orthogonal_sf is False
    assert node_channel.non_orth_delta == reference.non_orth_delta


def test_degrade_flag_is_no_op():
    base_sim = Simulator(num_nodes=1, packets_to_send=0, seed=42)
    degraded_sim = Simulator(num_nodes=1, packets_to_send=0, seed=42)

    apply_adr(base_sim)
    apply_adr(degraded_sim, degrade_channel=True, profile="urban")

    for base_ch, degraded_ch in zip(
        base_sim.multichannel.channels, degraded_sim.multichannel.channels
    ):
        assert isinstance(degraded_ch, Channel)
        assert degraded_ch.path_loss_exp == base_ch.path_loss_exp
        assert degraded_ch.shadowing_std == base_ch.shadowing_std
        assert degraded_ch.detection_threshold_dBm == base_ch.detection_threshold_dBm


def test_degrade_flag_preserves_pdr():
    sim_default = Simulator(
        num_nodes=1,
        num_gateways=1,
        area_size=4000,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=10,
        mobility=False,
        fixed_sf=7,
        seed=0,
    )
    apply_adr(sim_default)
    sim_default.run()
    pdr_default = sim_default.get_metrics()["PDR"]

    sim_flag = Simulator(
        num_nodes=1,
        num_gateways=1,
        area_size=4000,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=10,
        mobility=False,
        fixed_sf=7,
        seed=0,
    )
    apply_adr(sim_flag, degrade_channel=True)
    sim_flag.run()
    pdr_flag = sim_flag.get_metrics()["PDR"]

    assert pdr_flag == pytest.approx(pdr_default)
