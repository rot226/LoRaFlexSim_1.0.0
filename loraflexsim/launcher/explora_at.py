from __future__ import annotations

from .simulator import Simulator
from .channel import Channel


def apply(sim: Simulator) -> None:
    """Configure the EXPLoRa-AT ADR algorithm.

    This enables both node and server side ADR and initialises all nodes
    with parameters suitable for the EXPLoRa-AT strategy. Nodes start with a
    conservative spreading factor and maximum transmit power so that the
    network server can later optimise these values based on the measured SNR
    of the first uplinks.
    """
    # Typical installation margin for EXPLoRa-AT. Both the simulator and
    # the network server rely on this constant when evaluating SNR margins.
    Simulator.MARGIN_DB = 10.0
    from . import server as ns

    ns.MARGIN_DB = 10.0

    sim.adr_node = True
    sim.adr_server = True
    sim.network_server.adr_enabled = True
    sim.network_server.adr_method = "explora-at"

    for node in sim.nodes:
        # Start with the most robust SF so that connectivity is guaranteed
        # before the server sends optimised parameters based on the first
        # measurements.
        node.sf = 12
        node.initial_sf = 12
        node.channel.detection_threshold_dBm = (
            Channel.flora_detection_threshold(node.sf, node.channel.bandwidth)
            + node.channel.sensitivity_margin_dB
        )
        node.tx_power = 14.0
        node.initial_tx_power = 14.0
        node.adr_ack_cnt = 0
        node.adr_ack_limit = 64
        node.adr_ack_delay = 32

    for ch in sim.multichannel.channels:
        ch.detection_threshold_dBm = (
            Channel.flora_detection_threshold(12, ch.bandwidth)
            + ch.sensitivity_margin_dB
        )
