from simulateur_lora_sfrd.launcher import adr_standard_1
from simulateur_lora_sfrd.launcher.simulator import Simulator
from simulateur_lora_sfrd.launcher.channel import Channel


def test_apply_sets_flora_detection_threshold():
    sim = Simulator(num_nodes=1, packets_to_send=0)
    adr_standard_1.apply(sim, degrade_channel=True)
    node = sim.nodes[0]
    expected = Channel.FLORA_SENSITIVITY[node.sf][int(node.channel.bandwidth)]
    assert node.channel.detection_threshold_dBm == expected
