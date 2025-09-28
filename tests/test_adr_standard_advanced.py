import pytest

from loraflexsim.launcher import adr_standard_1
from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher.gateway import FLORA_NON_ORTH_DELTA
from loraflexsim.launcher.simulator import Simulator


def test_apply_preserves_base_channel_with_degrade_flag():
    base_channel = Channel(bandwidth=125_000, sensitivity_margin_dB=2.5)
    sim = Simulator(num_nodes=1, packets_to_send=0, channels=[base_channel])

    adr_standard_1.apply(
        sim,
        degrade_channel=True,
        profile="flora",
        capture_mode="advanced",
    )

    assert sim.multichannel.channels, "un canal doit être disponible"
    for channel in sim.multichannel.channels:
        assert isinstance(channel, Channel)
        assert channel.orthogonal_sf is False
        assert channel.non_orth_delta == FLORA_NON_ORTH_DELTA
        expected_threshold = Channel.flora_detection_threshold(12, channel.bandwidth)
        expected_threshold += channel.sensitivity_margin_dB
        assert channel.detection_threshold(12) == expected_threshold

    assert sim.channel is sim.multichannel.channels[0]
    assert sim.channel.orthogonal_sf is False
    assert sim.channel.non_orth_delta == FLORA_NON_ORTH_DELTA
    assert sim.network_server.channel is sim.channel


def test_profile_and_capture_parameters_are_ignored():
    custom_channel = Channel(
        bandwidth=125_000,
        path_loss_exp=3.1,
        shadowing_std=1.7,
        sensitivity_margin_dB=1.0,
    )
    sim = Simulator(num_nodes=1, packets_to_send=0, channels=[custom_channel])

    adr_standard_1.apply(
        sim,
        degrade_channel=True,
        profile="urban",
        capture_mode="advanced",
    )

    configured = sim.multichannel.channels[0]
    assert configured.path_loss_exp == pytest.approx(3.1)
    assert configured.shadowing_std == pytest.approx(1.7)
    assert configured.sensitivity_margin_dB == pytest.approx(1.0)
