from simulateur_lora_sfrd.launcher import adr_standard_1
from simulateur_lora_sfrd.launcher.simulator import Simulator
from simulateur_lora_sfrd.launcher.channel import Channel
from simulateur_lora_sfrd.launcher.node import Node


def test_apply_sets_flora_detection_threshold():
    sim = Simulator(num_nodes=1, packets_to_send=0)
    adr_standard_1.apply(sim, degrade_channel=True, profile="flora")
    node = sim.nodes[0]
    expected = Channel.FLORA_SENSITIVITY[node.sf][int(node.channel.bandwidth)]
    assert node.channel.detection_threshold_dBm == expected


def test_apply_sets_threshold_without_degradation():
    sim = Simulator(num_nodes=1, packets_to_send=0)
    adr_standard_1.apply(sim, degrade_channel=False)
    node = sim.nodes[0]
    expected = Channel.FLORA_SENSITIVITY[node.sf][int(node.channel.bandwidth)]
    assert node.channel.detection_threshold_dBm == expected


def test_threshold_updates_on_sf_change():
    sim = Simulator(num_nodes=1, packets_to_send=0)
    node = sim.nodes[0]
    node.sf = 10
    expected = Channel.FLORA_SENSITIVITY[10][int(node.channel.bandwidth)]
    assert node.channel.detection_threshold_dBm == expected


def test_threshold_updates_on_channel_change():
    sim = Simulator(num_nodes=1, packets_to_send=0)
    node = sim.nodes[0]
    new_channel = Channel(bandwidth=250e3)
    node.channel = new_channel
    expected = Channel.FLORA_SENSITIVITY[node.sf][250000]
    assert node.channel.detection_threshold_dBm == expected


def test_sensitivity_margin_offset():
    ch = Channel(bandwidth=125e3, sensitivity_margin_dB=5.0)
    node = Node(0, 0, 0, 7, 14, channel=ch)
    expected = Channel.FLORA_SENSITIVITY[7][125000] + 5.0
    assert node.channel.detection_threshold_dBm == expected
