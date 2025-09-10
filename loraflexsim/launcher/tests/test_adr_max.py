import random
from loraflexsim.launcher import adr_max
from loraflexsim.launcher.simulator import Simulator


def test_adr_max_sets_max_method():
    random.seed(0)
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        duty_cycle=None,
        mobility=False,
        seed=42,
    )
    adr_max.apply(sim)
    assert sim.adr_node is True
    assert sim.adr_server is True
    assert sim.network_server.adr_enabled is True
    assert sim.adr_method == "max"
    assert sim.network_server.adr_method == "max"
