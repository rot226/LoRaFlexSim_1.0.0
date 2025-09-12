import math

from loraflexsim.launcher.channel import Channel


def test_per_matches_croce_curve():
    ch = Channel(phy_model="omnet", use_flora_curves=False, shadowing_std=0.0)
    sf = 7
    # Points extraits de la courbe PER de Croce et al. (2018) pour un
    # paquet de 20 octets.
    reference = [
        (-9.5, 0.9285),
        (-7.5, 0.4363),
        (-5.5, 0.0550),
    ]
    for snr, expected in reference:
        per = ch.packet_error_rate(snr, sf, payload_bytes=20)
        assert math.isclose(per, expected, rel_tol=0.05)


def test_per_uses_flora_ber_model():
    ch = Channel(phy_model="omnet", use_flora_curves=False, shadowing_std=0.0, bandwidth=125e3)
    sf = 7
    snr = 0.0
    snir = 10 ** (snr / 10.0)
    from loraflexsim.launcher.omnet_modulation import calculate_ber_flora

    ber = calculate_ber_flora(snir, sf, ch.bandwidth)
    ser = 1.0 - (1.0 - ber) ** sf
    n_bits = 20 * 8
    per_bit = 1.0 - (1.0 - ber) ** n_bits
    n_sym = math.ceil(n_bits / sf)
    per_sym = 1.0 - (1.0 - ser) ** n_sym
    expected = max(per_bit, per_sym)
    per = ch.packet_error_rate(snr, sf, payload_bytes=20, ber_model="flora")
    assert math.isclose(per, expected, rel_tol=1e-9)
