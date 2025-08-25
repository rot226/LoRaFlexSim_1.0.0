import pytest
from loraflexsim.launcher.simulator import Simulator


def test_tx_energy_accounted_once():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=1,
        mobility=False,
        fixed_sf=7,
        fixed_tx_power=14.0,
        seed=0,
    )
    sim.run()
    node = sim.nodes[0]
    current = node.profile.get_tx_current(node.tx_power)
    airtime = node.channel.airtime(node.sf, payload_size=sim.payload_size_bytes)
    expected_tx = current * node.profile.voltage_v * (
        airtime + node.profile.ramp_up_s + node.profile.ramp_down_s
    )
    assert node.energy_tx == pytest.approx(expected_tx)
    expected_startup = (
        node.profile.startup_current_a
        * node.profile.voltage_v
        * node.profile.startup_time_s
        * 2
    )
    expected_preamble = (
        node.profile.preamble_current_a
        * node.profile.voltage_v
        * node.profile.preamble_time_s
    )
    assert node.energy_startup == pytest.approx(expected_startup)
    assert node.energy_preamble == pytest.approx(expected_preamble)
