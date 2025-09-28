import pytest

from loraflexsim.launcher.simulator import EventType, Simulator


def _advance_until_node_death(sim: Simulator, node, max_steps: int = 5000) -> None:
    """Fait avancer ``sim`` jusqu'à la mort de ``node`` ou échec."""

    for _ in range(max_steps):
        progressed = sim.step()
        if not progressed:
            pytest.fail("La file d'événements s'est vidée avant la mort du nœud.")
        if not node.alive:
            return
    pytest.fail("Le nœud n'est pas mort dans la limite de pas autorisée.")


def _drain_until_idle(sim: Simulator, max_steps: int = 5000) -> None:
    """Continue ``sim`` jusqu'à ce qu'aucun événement ne reste."""

    previous_remaining: int | None = None
    for _ in range(max_steps):
        progressed = sim.step()
        if not progressed:
            return
        current_remaining = sum(
            1 for evt in sim.event_queue if evt.type in (EventType.BEACON, EventType.PING_SLOT)
        )
        if previous_remaining is not None:
            assert current_remaining <= previous_remaining
        previous_remaining = current_remaining
    pytest.fail("La simulation ne s'est pas arrêtée comme prévu.")


@pytest.mark.parametrize(
    "node_class",
    ["B", "A"],
)
def test_simulator_stops_after_all_nodes_done(node_class: str) -> None:
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        area_size=1.0,
        transmission_mode="Periodic",
        packet_interval=1.0,
        first_packet_interval=0.1,
        packets_to_send=2,
        mobility=False,
        node_class=node_class,
        fixed_sf=7,
        fixed_tx_power=14,
        class_c_rx_interval=0.5,
        ping_slot_interval=1.0,
        battery_capacity_j=1e-9,
        seed=42,
    )

    node = sim.nodes[0]
    node.battery_remaining_j = 1e-9

    _advance_until_node_death(sim, node)

    assert sim._all_nodes_done()

    _drain_until_idle(sim)

    assert not sim.event_queue
    assert not sim.step()
