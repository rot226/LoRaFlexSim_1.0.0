import pytest

from simulateur_lora_sfrd.launcher.channel import Channel


def test_per_matches_cpp_impl():
    try:
        ch_cpp = Channel(phy_model="flora_cpp", use_flora_curves=True, shadowing_std=0.0)
    except OSError:
        pytest.skip("libflora_phy.so missing")

    ch_py = Channel(phy_model="flora_full", use_flora_curves=True, shadowing_std=0.0)

    snr = 5.0
    sf = 7
    per_cpp = ch_cpp.packet_error_rate(snr, sf, payload_bytes=20)
    per_py = ch_py.packet_error_rate(snr, sf, payload_bytes=20)

    assert abs(per_cpp - per_py) <= 1e-6
