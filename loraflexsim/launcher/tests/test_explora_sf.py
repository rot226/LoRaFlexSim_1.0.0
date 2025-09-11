import random
from loraflexsim.launcher.simulator import Simulator
from loraflexsim.launcher import explora_sf


def test_explora_sf_assigns_groups():
    random.seed(0)
    sim = Simulator(
        num_nodes=6,
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
    gw = sim.gateways[0]
    rssis = [-40, -50, -60, -70, -80, -90]
    for node, rssi in zip(sim.nodes, rssis):
        frame = node.prepare_uplink(b"ping")
        sim.network_server.receive(0, node.id, gw.id, rssi, frame)
    for i, node in enumerate(sim.nodes):
        dl = gw.pop_downlink(node.id)
        assert dl is not None
        node.handle_downlink(dl)
        assert node.sf == 7 + i


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
