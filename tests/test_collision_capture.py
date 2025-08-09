from simulateur_lora_sfrd.launcher.gateway import Gateway
from simulateur_lora_sfrd.launcher.server import NetworkServer


def _setup():
    gw = Gateway(0, 0, 0)
    server = NetworkServer()
    server.gateways = [gw]
    return gw, server


def test_same_sf_collision():
    gw, server = _setup()
    # two transmissions start at the same time with same SF/frequency
    gw.start_reception(1, 1, 7, -50, 0.1, 6.0, 0.0, 868e6)
    gw.start_reception(2, 2, 7, -58, 0.1, 6.0, 0.0, 868e6)
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)
    assert server.packets_received == 0


def test_capture_after_five_preamble():
    gw, server = _setup()
    sf = 7
    symbol_time = (2 ** sf) / 125e3
    start2 = 5.1 * symbol_time
    gw.start_reception(1, 1, sf, -50, 0.1, 6.0, 0.0, 868e6)
    gw.start_reception(2, 2, sf, -60, 0.1, 6.0, start2, 868e6)
    gw.end_reception(1, server, 1)
    gw.end_reception(2, server, 2)
    assert server.packets_received == 1

