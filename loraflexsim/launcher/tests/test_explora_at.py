from loraflexsim.launcher.server import NetworkServer
from loraflexsim.launcher.node import Node
from loraflexsim.launcher.channel import Channel


def test_explora_at_computation_and_power_application():
    server = NetworkServer()
    channel = Channel()
    server.channel = channel
    node = Node(1, 0.0, 0.0, sf=12, tx_power=14.0)
    server.nodes = [node]

    noise = channel.noise_floor_dBm()
    sf, power, interval = server.explora_at(node.id, noise + 40.0)
    assert sf == 7
    assert power == 11.0
    assert interval == 1.0
    assert node.tx_power == 11.0

    sf2, power2, interval2 = server.compute_explora_at(node, noise - 30.0)
    assert sf2 == 12
    assert power2 == 14.0
    assert node.tx_power == 11.0
    assert interval2 == 32.0
