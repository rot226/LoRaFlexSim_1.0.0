import random

from loraflexsim.launcher.simulator import Simulator
from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher import explora_at, server


def test_explora_at_enables_adr_and_sets_method():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        duty_cycle=None,
        mobility=False,
        adr_node=False,
        adr_server=False,
        seed=1,
    )
    explora_at.apply(sim)
    assert sim.adr_node is True
    assert sim.adr_server is True
    assert sim.network_server.adr_method == "explora-at"


def test_explora_at_initialisation_margin_and_sf():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        duty_cycle=None,
        mobility=False,
        adr_node=False,
        adr_server=False,
        seed=1,
    )
    explora_at.apply(sim)
    node = sim.nodes[0]
    assert Simulator.MARGIN_DB == 10.0
    assert server.MARGIN_DB == 10.0
    assert node.sf == node.initial_sf == 12
    expected_thr = Channel.flora_detection_threshold(12, node.channel.bandwidth) + node.channel.sensitivity_margin_dB
    assert node.channel.detection_threshold_dBm == expected_thr


def test_explora_at_uniform_airtime_groups():
    random.seed(0)
    sim = Simulator(
        num_nodes=12,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        duty_cycle=None,
        mobility=False,
        adr_node=False,
        adr_server=False,
        seed=42,
    )
    explora_at.apply(sim)
    gw = sim.gateways[0]
    rssis = [-40, -41, -55, -56, -70, -71, -85, -86, -100, -101, -115, -116]
    for i, (node, rssi) in enumerate(zip(sim.nodes, rssis)):
        frame = node.prepare_uplink(b"ping")
        sim.network_server.receive(i, node.id, gw.id, rssi, frame)
    for node in sim.nodes:
        dl = gw.pop_downlink(node.id)
        if dl is not None:
            node.handle_downlink(dl)
    counts = {sf: 0 for sf in range(7, 13)}
    for node in sim.nodes:
        counts[node.sf] += 1
        expected = Channel.flora_detection_threshold(node.sf, node.channel.bandwidth) + node.channel.sensitivity_margin_dB
        assert node.channel.detection_threshold_dBm == expected
    assert counts[7] == 6
    assert counts[8] == 3
    assert counts[9] == 2
    assert counts[10] == 1
    assert counts[11] == 0
    assert counts[12] == 0
