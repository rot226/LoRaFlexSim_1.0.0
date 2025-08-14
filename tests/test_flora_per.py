import math

from simulateur_lora_sfrd.launcher.channel import Channel


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
