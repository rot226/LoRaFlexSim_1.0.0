from loraflexsim.launcher.simulator import Simulator
from loraflexsim.launcher import radr


def test_radr_apply_and_model_update():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        mobility=False,
        adr_node=False,
        adr_server=False,
        duty_cycle=None,
        seed=1,
    )
    radr.apply(sim)
    assert sim.network_server.adr_method == "radr"
    assert hasattr(sim.network_server, "adr_model")

    state = ("s",)
    action = "a"
    sim.network_server.adr_reward(state, action, True)
    assert sim.network_server.adr_model.q_table[(state, action)] == 1.0
    sim.network_server.adr_reward(state, action, False)
    assert sim.network_server.adr_model.q_table[(state, action)] == 0.0
