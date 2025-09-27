from loraflexsim.launcher.simulator import Simulator


def test_simulator_without_class_b_nodes_has_no_beacons():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        packets_to_send=1,
        node_class="C",
        mobility=False,
        max_sim_time=50.0,
        packet_interval=1.0,
        seed=42,
    )

    assert sim.last_beacon_time is None
    assert sim.network_server.last_beacon_time is None

    sim.run()

    assert sim.current_time < sim.max_sim_time
    assert sim.current_time < sim.max_sim_time / 2
    assert not sim.event_queue
    assert sim.network_server.last_beacon_time is None

