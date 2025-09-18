from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher.gateway import Gateway, FLORA_NON_ORTH_DELTA
from loraflexsim.launcher.server import NetworkServer


def test_orthogonal_sf_no_collision():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    gw.start_reception(
        1, 1, 7, -60, 1.0, 6.0, 0.0, 868e6, orthogonal_sf=True
    )
    gw.start_reception(
        2, 2, 9, -60, 1.0, 6.0, 0.0, 868e6, orthogonal_sf=True
    )
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    assert server.packets_received == 2


def test_capture_requires_five_symbols():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    # Strong signal starts first
    gw.start_reception(1, 1, 7, -50, 1.0, 6.0, 0.0, 868e6)
    # Weaker packet starts after more than 5 symbols
    gw.start_reception(2, 2, 7, -60, 1.0, 6.0, 0.006, 868e6)
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    assert server.packets_received == 1


def test_no_capture_before_five_symbols():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    # Strong signal starts first but second arrives too soon
    gw.start_reception(1, 1, 7, -50, 1.0, 6.0, 0.0, 868e6)
    gw.start_reception(2, 2, 7, -60, 1.0, 6.0, 0.003, 868e6)
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    assert server.packets_received == 0


def test_strong_signal_arrives_late():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    # Weak packet first
    gw.start_reception(1, 1, 7, -60, 1.0, 6.0, 0.0, 868e6)
    # Strong packet after 5 symbols should not capture
    gw.start_reception(2, 2, 7, -50, 1.0, 6.0, 0.006, 868e6)
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    assert server.packets_received == 0


def test_cross_sf_collision():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    # Two packets on the same frequency with different SF collide
    gw.start_reception(
        1, 1, 7, -60, 1.0, 6.0, 0.0, 868e6,
        orthogonal_sf=False,
        non_orth_delta=FLORA_NON_ORTH_DELTA,
    )
    gw.start_reception(
        2, 2, 9, -60, 1.0, 6.0, 0.0, 868e6,
        orthogonal_sf=False,
        non_orth_delta=FLORA_NON_ORTH_DELTA,
    )
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    assert server.packets_received == 0


def test_cross_sf_capture_after_delay():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    # Strong signal starts first and should capture the weaker one
    gw.start_reception(
        1, 1, 7, -50, 1.0, 6.0, 0.0, 868e6,
        orthogonal_sf=False,
        non_orth_delta=FLORA_NON_ORTH_DELTA,
    )
    # Weaker packet with higher SF starts after more than 5 of its symbols
    gw.start_reception(
        2, 2, 9, -60, 1.0, 6.0, 0.03, 868e6,
        orthogonal_sf=False,
        non_orth_delta=FLORA_NON_ORTH_DELTA,
    )
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    assert server.packets_received == 1


def test_non_orth_same_sf_uses_capture_threshold():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    # Two packets with the same SF start simultaneously with a 5 dB RSSI gap.
    # With ``orthogonal_sf`` disabled, the capture matrix should NOT apply to
    # same-SF collisions, so the regular capture threshold (6 dB) must be used.
    gw.start_reception(
        1,
        1,
        7,
        -50,
        1.0,
        6.0,
        0.0,
        868e6,
        orthogonal_sf=False,
        non_orth_delta=FLORA_NON_ORTH_DELTA,
        capture_window_symbols=0,
    )
    gw.start_reception(
        2,
        2,
        7,
        -55,
        1.0,
        6.0,
        0.0,
        868e6,
        orthogonal_sf=False,
        non_orth_delta=FLORA_NON_ORTH_DELTA,
        capture_window_symbols=0,
    )
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    # RSSI difference (5 dB) is below capture threshold (6 dB) so none captured
    assert server.packets_received == 0


def test_flora_capture_requires_six_symbols():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    channel = Channel(phy_model="flora", shadowing_std=0.0, use_flora_curves=True)
    flora_phy = channel.flora_phy
    assert flora_phy is not None
    assert channel.capture_window_symbols == 6

    sf = 7
    symbol_time = (2 ** sf) / channel.bandwidth
    strong_start = 0.0
    strong_end = strong_start + symbol_time * 10
    weak_start = strong_start + 1.5 * symbol_time
    weak_end = weak_start + symbol_time  # ends between the 5th and 6th symbols

    gw.start_reception(
        1,
        1,
        sf,
        -50,
        strong_end,
        channel.capture_threshold_dB,
        strong_start,
        868e6,
        capture_mode="flora",
        flora_phy=flora_phy,
        capture_window_symbols=channel.capture_window_symbols,
    )
    gw.start_reception(
        2,
        2,
        sf,
        -50,
        weak_end,
        channel.capture_threshold_dB,
        weak_start,
        868e6,
        capture_mode="flora",
        flora_phy=flora_phy,
        capture_window_symbols=channel.capture_window_symbols,
    )

    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    # The weaker packet still overlaps when only five symbols were clean, so
    # FLoRa's receiver (which requires six symbols) reports a collision.
    assert server.packets_received == 0
