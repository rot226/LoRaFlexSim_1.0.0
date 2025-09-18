import pytest

from loraflexsim.launcher.simulator import Simulator


@pytest.mark.xfail(reason="L'énergie de rampe n'est pas exposée séparément", strict=True)
def test_energy_breakdown_reports_pa_ramp_component():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=1,
        mobility=False,
        seed=0,
    )
    sim.run()
    breakdown = sim.nodes[0].get_energy_breakdown()
    assert "ramp" in breakdown
