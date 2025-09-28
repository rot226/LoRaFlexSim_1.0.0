from loraflexsim.launcher.simulator import Simulator
from loraflexsim.launcher.adr_standard_1 import apply as apply_adr
from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher.lorawan import TX_POWER_INDEX_TO_DBM
import loraflexsim.launcher.server as server


def _run(distance: float, initial_sf: int = 12, packets: int = 30):
    ch = Channel(shadowing_std=0.0, fast_fading_std=0.0, noise_floor_std=0.0)
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=packets,
        mobility=False,
        adr_server=True,
        adr_method="avg",
        channels=[ch],
        seed=1,
    )
    apply_adr(sim)
    node = sim.nodes[0]
    gw = sim.gateways[0]
    node.x = 0.0
    node.y = 0.0
    gw.x = distance
    gw.y = 0.0
    node.sf = initial_sf
    node.initial_sf = initial_sf
    sim.run()
    return node


def test_adr_decreases_sf_with_good_link():
    node = _run(distance=1.0)
    assert node.sf == 7
    assert node.tx_power == TX_POWER_INDEX_TO_DBM[6]


def test_adr_increases_sf_with_poor_link():
    node = _run(distance=10000.0, initial_sf=8)
    assert node.sf == 7
    assert node.tx_power == TX_POWER_INDEX_TO_DBM[3]


def test_shared_channel_threshold_remains_sf_specific():
    sim = Simulator(
        num_nodes=2,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        mobility=False,
        adr_node=False,
        adr_server=False,
        duty_cycle=None,
        seed=2,
    )
    apply_adr(sim)
    node_a, node_b = sim.nodes
    gw = sim.gateways[0]
    ns = sim.network_server

    assert node_a.channel is node_b.channel, "Les deux nœuds doivent partager le même canal"

    noise = ns.channel.noise_floor_dBm()
    high_rssi = noise + server.REQUIRED_SNR[7] + server.MARGIN_DB + 6.0
    for i in range(1, 21):
        ns.receive(i, node_a.id, gw.id, high_rssi)

    assert node_a.sf == 7
    assert node_b.sf == 12

    channel = node_b.channel
    expected_sf12 = Channel.flora_detection_threshold(12, channel.bandwidth)
    expected_sf12 += channel.sensitivity_margin_dB

    assert channel.detection_threshold(node_b.sf) == expected_sf12
    assert channel.detection_threshold_dBm == -float("inf")

    rssi = expected_sf12 + 0.2
    sf7_threshold = Channel.flora_detection_threshold(7, channel.bandwidth)
    sf7_threshold += channel.sensitivity_margin_dB
    assert rssi < sf7_threshold, "Le RSSI choisi doit rester insuffisant pour SF7"
    assert rssi >= channel.detection_threshold(node_b.sf)
