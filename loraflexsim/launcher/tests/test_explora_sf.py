import random
from loraflexsim.launcher.simulator import Simulator
from loraflexsim.launcher import explora_sf
from loraflexsim.launcher.server import REQUIRED_SNR, MARGIN_DB


def test_explora_sf_assigns_optimal_sf():
    random.seed(0)
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        duty_cycle=None,
        mobility=False,
        adr_node=False,
        adr_server=False,
        seed=42,
    )
    explora_sf.apply(sim)
    node = sim.nodes[0]
    gw = sim.gateways[0]
    rssi = -40
    frame = node.prepare_uplink(b"ping")
    sim.network_server.receive(0, node.id, gw.id, rssi, frame)
    dl = gw.pop_downlink(node.id)
    assert dl is not None
    node.handle_downlink(dl)
    snr = rssi - node.channel.noise_floor_dBm()
    expected_sf = 12
    for sf in range(7, 13):
        if snr >= REQUIRED_SNR.get(sf, -20.0) + MARGIN_DB:
            expected_sf = sf
            break
    assert node.sf == expected_sf


def test_explora_sf_sets_adr_method():
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
    explora_sf.apply(sim)
    assert sim.network_server.adr_method == "explora-sf"
