import math

from simulateur_lora_sfrd.launcher.omnet_modulation import calculate_ber, calculate_ser


def test_calculate_ser_matches_ber_conversion():
    snir = 5.0
    bandwidth = 125000.0
    bitrate = 5468.75
    ber = calculate_ber(snir, bandwidth, bitrate)
    expected_ser = 1.0 - (1.0 - ber) ** 4
    assert math.isclose(calculate_ser(snir, bandwidth, bitrate), expected_ser, rel_tol=1e-9)
