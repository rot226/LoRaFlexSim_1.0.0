from simulateur_lora_sfrd.launcher.simulator import Simulator


def test_tx_power_distribution_counts():
    sim = Simulator(
        num_nodes=2,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=1,
        mobility=False,
        seed=0,
    )
    sim.nodes[0].tx_power = 14.0
    sim.nodes[1].tx_power = 17.0
    sim.run()
    metrics = sim.get_metrics()
    assert metrics["tx_power_distribution"] == {14.0: 1, 17.0: 1}
