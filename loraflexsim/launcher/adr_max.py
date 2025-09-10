from __future__ import annotations

from .simulator import Simulator


def apply(sim: Simulator) -> None:
    """Configure ADR variant adr_max."""
    Simulator.MARGIN_DB = 15.0
    sim.adr_node = True
    sim.adr_server = True
    sim.adr_method = "max"
    sim.network_server.adr_enabled = True
    sim.network_server.adr_method = "max"
    for node in sim.nodes:
        node.adr_ack_cnt = 0
        node.adr_ack_limit = 64
        node.adr_ack_delay = 32
