from __future__ import annotations

from .simulator import Simulator
from .channel import Channel


def apply(sim: Simulator) -> None:
    """Configure the EXPLoRa-SF ADR algorithm.

    Nodes and the network server start with conservative defaults so the
    server can quickly refine them after the first uplinks.  Each node is
    initialised on SF12 with a 14 dBm transmit power and both sides enable
    ADR using the ``explora-sf`` method.
    """
    # Typical installation margin for EXPLoRa-SF. Both the simulator and the
    # network server rely on this constant when evaluating SNR margins.
    Simulator.MARGIN_DB = 15.0
    from . import server as ns

    ns.MARGIN_DB = 15.0

    sim.adr_node = True
    sim.adr_server = True
    sim.network_server.adr_enabled = True
    sim.network_server.adr_method = "explora-sf"

    for node in sim.nodes:
        # Start with the most robust SF so that connectivity is guaranteed
        # before the server sends an optimised value based on the first
        # measurements.
        node.sf = node.initial_sf = 12
        node.tx_power = node.initial_tx_power = 14.0
        node.adr_ack_cnt = 0
        node.adr_ack_limit = 64
        node.adr_ack_delay = 32

    # Les canaux conservent désormais un seuil neutre ; la sensibilité SF est
    # évaluée lorsque les paquets sont traités.
