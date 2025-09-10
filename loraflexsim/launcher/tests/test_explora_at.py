from loraflexsim.launcher.simulator import Simulator
from loraflexsim.launcher import explora_at


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
