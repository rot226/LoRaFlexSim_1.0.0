from simulateur_lora_sfrd.launcher.gateway import Gateway
from simulateur_lora_sfrd.launcher.server import NetworkServer


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
    gw.start_reception(1, 1, 7, -60, 1.0, 6.0, 0.0, 868e6, orthogonal_sf=False)
    gw.start_reception(2, 2, 9, -60, 1.0, 6.0, 0.0, 868e6, orthogonal_sf=False)
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    assert server.packets_received == 0


def test_cross_sf_capture_after_delay():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]

    # Strong signal starts first and should capture the weaker one
    gw.start_reception(1, 1, 7, -50, 1.0, 6.0, 0.0, 868e6, orthogonal_sf=False)
    # Weaker packet with higher SF starts after more than 5 of its symbols
    gw.start_reception(2, 2, 9, -60, 1.0, 6.0, 0.03, 868e6, orthogonal_sf=False)
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)

    assert server.packets_received == 1
