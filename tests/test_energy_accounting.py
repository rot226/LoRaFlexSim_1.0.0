import pytest
from simulateur_lora_sfrd.launcher.simulator import Simulator


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
    expected = (
        node.profile.get_tx_current(node.tx_power)
        * node.profile.voltage_v
        * node.channel.airtime(node.sf, payload_size=sim.payload_size_bytes)
    )
    assert node.energy_tx == pytest.approx(expected)
