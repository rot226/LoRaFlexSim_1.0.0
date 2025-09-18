"""Tests ensuring FLoRa configurations use the non-orthogonal capture matrix by default."""

from loraflexsim.launcher.gateway import FLORA_NON_ORTH_DELTA
from loraflexsim.launcher.simulator import Simulator


def test_flora_simulator_uses_non_orthogonal_capture():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        flora_mode=True,
        phy_model="omnet_full",
        packets_to_send=1,
        mobility=False,
        duty_cycle=None,
        warm_up_intervals=0,
        log_mean_after=None,
        seed=1234,
    )

    # The main channel and all nodes should immediately use the FLoRa matrix
    assert sim.channel.orthogonal_sf is False
    assert sim.channel.non_orth_delta == FLORA_NON_ORTH_DELTA

    node = sim.nodes[0]
    assert node.channel.orthogonal_sf is False
    assert node.channel.non_orth_delta == FLORA_NON_ORTH_DELTA
