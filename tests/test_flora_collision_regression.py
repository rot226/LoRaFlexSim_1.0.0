"""Test de régression : toute superposition en mode FLoRa provoque une collision."""

from loraflexsim.launcher.simulator import Simulator


def test_flora_mode_counts_collisions_without_overlap_margin():
    sim = Simulator(
        num_nodes=2,
        num_gateways=1,
        flora_mode=True,
        phy_model="omnet_full",
        packets_to_send=1,
        mobility=False,
        duty_cycle=None,
        warm_up_intervals=0,
        log_mean_after=None,
        area_size=1.0,
        fixed_sf=7,
        fixed_tx_power=14.0,
        seed=12345,
    )

    for node in sim.nodes:
        sim.schedule_event(node, 0.0, reason="test")

    while sim.step():
        pass

    metrics = sim.get_metrics()
    sim.stop()

    assert sim.packets_lost_collision > 0
    assert metrics["collisions"] > 0
