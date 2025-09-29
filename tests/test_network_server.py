import pytest

from loraflexsim.launcher.server import ADR_WINDOW_SIZE, NetworkServer
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


def test_packet_below_energy_detection_threshold_ignored():
    server = NetworkServer(energy_detection_dBm=-90.0)
    gateway = Gateway(0, 0, 0)
    node = Node(0, 0, 0, 7, 14)
    server.gateways = [gateway]
    server.nodes = [node]

    server.receive(1, node.id, gateway.id, rssi=-95.0, snir=-5.0)

    assert server.packets_received == 0
    assert server.duplicate_packets == 0
    assert 1 not in server.received_events
    assert 1 not in server.event_gateway
    assert node.last_rssi is None
    assert getattr(node, "last_snr", None) is None


def test_add_gateway_deduplicates():
    server = SimpleServer()
    gw = Gateway(0, 0, 0)
    server.add_gateway(gw)
    server.add_gateway(gw)
    assert server.gateways == [gw]


def test_multi_gateway_adr_history_evolution():
    server = NetworkServer()
    gw1 = Gateway(0, 0, 0)
    gw2 = Gateway(1, 100, 0)
    node = Node(0, 0, 0, 7, 14)
    server.gateways = [gw1, gw2]
    server.nodes = [node]

    server.receive(1, node.id, gw1.id, snir=2.5)
    assert node.gateway_snr_history.get(gw1.id, []) == [2.5]
    assert node.gateway_snr_history.get(gw2.id, []) == []

    server.receive(2, node.id, gw2.id, snir=4.0)
    assert node.gateway_snr_history.get(gw1.id, []) == [2.5]
    assert node.gateway_snr_history.get(gw2.id, []) == [4.0]

    server.receive(3, node.id, gw1.id, snir=3.0)
    assert node.gateway_snr_history.get(gw1.id, []) == [2.5, 3.0]
    assert node.gateway_snr_history.get(gw2.id, []) == [4.0]

    server.receive(3, node.id, gw2.id, snir=5.0)
    assert node.gateway_snr_history.get(gw1.id, []) == [2.5]
    assert node.gateway_snr_history.get(gw2.id, []) == [4.0, 5.0]

    for event_id in range(4, 4 + ADR_WINDOW_SIZE):
        snr = float(event_id)
        server.receive(event_id, node.id, gw2.id, snir=snr)

    history_gw2 = node.gateway_snr_history.get(gw2.id, [])
    assert len(history_gw2) == ADR_WINDOW_SIZE
    assert history_gw2[-1] == float(3 + ADR_WINDOW_SIZE)


def test_adr_max_does_not_raise_sf_when_power_already_max():
    server = NetworkServer(adr_method="adr-max")
    server.adr_enabled = True

    gateway = Gateway(0, 0, 0)
    node = Node(0, 0, 0, 7, 14)
    server.gateways = [gateway]
    server.nodes = [node]

    for event_id in range(1, ADR_WINDOW_SIZE + 1):
        server.receive(event_id, node.id, gateway.id, snir=-5.0)

    assert node.sf == 7
    assert node.tx_power == 14


def test_duplicate_with_nearly_identical_snr_removes_previous_sample():
    server = NetworkServer()
    gw1 = Gateway(0, 0, 0)
    gw2 = Gateway(1, 10, 0)
    node = Node(0, 0, 0, 7, 14)
    server.gateways = [gw1, gw2]
    server.nodes = [node]

    event_id = 42
    initial_snr = 5.0
    tiny_delta = 5e-10

    server.receive(event_id, node.id, gw1.id, snir=initial_snr)
    assert node.gateway_snr_history.get(gw1.id, []) == [initial_snr]

    server.receive(event_id, node.id, gw2.id, snir=initial_snr + tiny_delta)

    assert node.gateway_snr_history.get(gw1.id, []) == []
    assert pytest.approx(
        node.gateway_snr_history.get(gw2.id, [])[0], abs=1e-9
    ) == initial_snr + tiny_delta
    assert server.duplicate_packets == 1
