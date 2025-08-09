from simulateur_lora_sfrd.launcher.server import NetworkServer
from simulateur_lora_sfrd.launcher.gateway import Gateway
from simulateur_lora_sfrd.launcher.node import Node


def test_deduplicate_packets():
    server = NetworkServer()
    gw1 = Gateway(0, 0, 0)
    gw2 = Gateway(1, 10, 0)
    node = Node(0, 0, 0, 7, 14)
    server.gateways = [gw1, gw2]
    server.nodes = [node]

    server.receive(1, node.id, gw1.id, -20)
    server.receive(1, node.id, gw2.id, -22)

    assert server.packets_received == 1
    assert server.duplicate_packets == 1
    assert server.event_gateway[1] == gw1.id
