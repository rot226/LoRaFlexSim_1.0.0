import pytest

from loraflexsim.launcher.simulator import Simulator


def test_class_c_termination_stops_event_loop():
    sim = Simulator(
        num_nodes=2,
        num_gateways=1,
        area_size=1.0,
        transmission_mode="Periodic",
        packet_interval=1.0,
        first_packet_interval=0.1,
        packets_to_send=2,
        mobility=False,
        node_class="C",
        fixed_sf=7,
        fixed_tx_power=14,
        class_c_rx_interval=0.5,
        seed=123,
    )

    node_a = sim.nodes[0]
    node_b = sim.nodes[1]
    node_a.battery_capacity_j = 0.002
    node_a.battery_remaining_j = 0.002

    max_steps = 5000
    progressed = True
    for _ in range(max_steps):
        progressed = sim.step()
        if not progressed:
            break
        if not node_a.alive and node_b.packets_sent >= sim.packets_to_send:
            break
    else:
        pytest.fail(
            "Les conditions de terminaison (mort d'un nœud et quota atteint) ne se sont pas produites."
        )

    assert not node_a.alive
    assert node_a.packets_sent < sim.packets_to_send
    assert node_b.packets_sent >= sim.packets_to_send
    assert progressed

    for _ in range(max_steps):
        progressed = sim.step()
        if not progressed:
            break
    else:
        pytest.fail("La simulation ne s'est pas arrêtée après la mort et le quota atteints.")

    assert not progressed
    assert not sim.event_queue

    metrics_len = len(sim.metrics_timeline)
    assert not sim.step()
    assert len(sim.metrics_timeline) == metrics_len
