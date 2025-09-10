from __future__ import annotations

"""Rapid ADR configuration for LoRaFlexSim.

This module configures the simulator to use a simplified and reactive ADR
strategy.  Adaptation relies on fixed SNR thresholds and applies larger steps
than the standard LoRaWAN algorithm to converge quickly.
"""

from .simulator import Simulator
from .channel import Channel
from .lorawan import TX_POWER_INDEX_TO_DBM

# High and low SNR thresholds in dB used to trigger rate adaptation
SNR_HIGH_THRESHOLD = 10.0
SNR_LOW_THRESHOLD = 0.0

# Fast adjustment steps
SF_STEP = 1
POWER_STEP_INDEX = 1  # 1 index = 2 dB


def apply(sim: Simulator) -> None:
    """Enable rapid ADR with predefined thresholds on ``sim``.

    The function enables ADR on both nodes and server and configures the
    network server with the high/low SNR thresholds as well as the adjustment
    step sizes.
    """

    Simulator.MARGIN_DB = 15.0
    sim.adr_node = True
    sim.adr_server = True
    sim.network_server.adr_enabled = True
    sim.network_server.adr_strategy = "radr"
    sim.network_server.snr_high_threshold = SNR_HIGH_THRESHOLD
    sim.network_server.snr_low_threshold = SNR_LOW_THRESHOLD
    sim.network_server.sf_step = SF_STEP
    sim.network_server.power_step = POWER_STEP_INDEX

    for node in sim.nodes:
        # Start from the most robust settings
        node.sf = 12
        node.initial_sf = 12
        max_tx_power = TX_POWER_INDEX_TO_DBM[0]
        node.tx_power = max_tx_power
        node.initial_tx_power = max_tx_power
        node.adr_ack_cnt = 0
        node.adr_ack_limit = 64
        node.adr_ack_delay = 32
        # Update sensitivity threshold according to initial SF
        node.channel.detection_threshold_dBm = Channel.flora_detection_threshold(
            node.sf, node.channel.bandwidth
        ) + node.channel.sensitivity_margin_dB
