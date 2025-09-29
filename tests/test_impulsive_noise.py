import math

import pytest

from loraflexsim.launcher.channel import Channel
from traffic.rng_manager import RngManager


def test_impulsive_noise_increases_floor():
    mgr = RngManager(0)
    base = Channel(
        noise_floor_std=0.0,
        variable_noise_std=0.0,
        fine_fading_std=0.0,
        rng=mgr.get_stream("base", 0),
    )
    ch = Channel(
        noise_floor_std=0.0,
        variable_noise_std=0.0,
        fine_fading_std=0.0,
        impulsive_noise_prob=1.0,
        impulsive_noise_dB=20.0,
        rng=mgr.get_stream("ch", 0),
    )
    assert ch.noise_floor_dBm() >= base.noise_floor_dBm() + 19.0


def test_noise_floor_sums_interference_in_linear_domain():
    mgr = RngManager(0)
    channel = Channel(
        noise_floor_std=0.0,
        variable_noise_std=0.0,
        fine_fading_std=0.0,
        rng=mgr.get_stream("linear", 0),
    )
    channel.noise_figure_dB = 0.0
    channel.interference_dB = -110.0
    channel.band_interference = [
        (channel.frequency_hz, channel.bandwidth, -115.0),
        (channel.frequency_hz + channel.bandwidth / 4.0, channel.bandwidth, -118.0),
    ]
    channel.adjacent_interference_dB = 0.0
    channel.humidity_noise_coeff_dB = 0.0
    channel.impulsive_noise_prob = 0.0

    measured = channel.omnet_phy.noise_floor()

    eff_bw = min(channel.bandwidth, channel.frontend_filter_bw)
    thermal = channel.omnet_phy.model.thermal_noise_dBm(eff_bw)
    base_power = 10 ** ((thermal + channel.noise_figure_dB) / 10.0)
    expected_power = base_power
    expected_power += 10 ** (channel.interference_dB / 10.0)
    expected_power += 10 ** (-115.0 / 10.0)
    expected_power += 10 ** (-118.0 / 10.0)
    expected = 10 * math.log10(expected_power)

    assert measured == pytest.approx(expected, rel=1e-6)
