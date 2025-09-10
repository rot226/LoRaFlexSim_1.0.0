from __future__ import annotations

"""Configuration helper for the Explora-AT adaptive algorithm.

The module exposes a single :func:`apply` function mirroring the style of the
existing ADR helpers.  ``Explora‑AT`` initialises nodes so that both the server
and the nodes can later adapt the spreading factor, transmission power and the
recommended inter‑packet interval.
"""

from .simulator import Simulator
from .channel import Channel


def apply(sim: Simulator) -> None:
    """Configure *Explora‑AT* on ``sim``.

    The helper simply prepares every node with common initial parameters
    (SF7 and 14 dBm) and ensures the channel detection threshold matches
    the chosen spreading factor.  No ADR is enabled so that the dedicated
    Explora logic in :class:`~loraflexsim.launcher.server.NetworkServer`
    can be used instead.
    """

    sim.adr_node = False
    sim.adr_server = False
    for node in sim.nodes:
        node.sf = 7
        node.initial_sf = 7
        node.channel.detection_threshold_dBm = Channel.flora_detection_threshold(
            node.sf, node.channel.bandwidth
        ) + node.channel.sensitivity_margin_dB
        node.tx_power = 14.0
        node.initial_tx_power = 14.0
