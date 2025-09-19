import pytest

from loraflexsim.launcher.server import NetworkServer
from loraflexsim.launcher.gateway import Gateway
from loraflexsim.launcher.node import Node
from loraflexsim.architecture import NetworkServer as SimpleServer



def test_deduplicate_packets():
    server = NetworkServer()
    gw1 = Gateway(0, 0, 0)
    gw2 = Gateway(1, 10, 0)
    node = Node(0, 0, 0, 7, 14)
    server.gateways = [gw1, gw2]
    server.nodes = [node]

    server.receive(1, node.id, gw1.id, -20, snir=5.0)
    server.receive(1, node.id, gw2.id, -22, snir=8.5)

    assert server.packets_received == 1
    assert server.duplicate_packets == 1
    assert server.event_gateway[1] == gw2.id
    assert pytest.approx(server.event_snir[1], abs=1e-9) == 8.5
    assert node.last_snr == 8.5
    assert node.gateway_snr_history.get(gw1.id, []) == []
    assert node.gateway_snr_history.get(gw2.id, []) == [8.5]


def test_add_gateway_deduplicates():
    server = SimpleServer()
    gw = Gateway(0, 0, 0)
    server.add_gateway(gw)
    server.add_gateway(gw)
    assert server.gateways == [gw]
