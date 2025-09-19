"""Compare ADR Standard decisions against a reference FLoRa trace."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from loraflexsim.launcher import Simulator
from loraflexsim.launcher.adr_standard_1 import apply as apply_adr_standard
from loraflexsim.launcher.lorawan import (
    DR_TO_SF,
    LinkADRReq,
    TX_POWER_INDEX_TO_DBM,
)

DATA_PATH = (
    Path(__file__).resolve().parent / "data" / "flora_multi_gateway_txconfig.json"
)


@pytest.mark.integration
def test_adr_standard_alignment_with_flora_trace():
    """Ensure ADR standard reproduces the FLoRa TXCONFIG decisions."""

    with DATA_PATH.open("r", encoding="utf-8") as handle:
        events = json.load(handle)

    sim = Simulator(
        num_nodes=1,
        num_gateways=2,
        area_size=1000.0,
        packet_interval=1200.0,
        first_packet_interval=5.0,
        packets_to_send=0,
        flora_mode=True,
        flora_timing=False,
        adr_server=True,
        adr_method="avg",
        seed=42,
    )
    apply_adr_standard(sim)

    node = sim.nodes[0]
    server = sim.network_server

    # Clean scheduler state for a deterministic comparison
    server.scheduler.queue.clear()

    last_expected_sf = node.sf
    last_expected_power = node.tx_power

    for entry in events:
        event_id = entry["event_id"]
        best_gateway = entry["best_gateway"]
        gateway_info = entry["gateways"][str(best_gateway)]
        snr = gateway_info["snr"]
        rssi = gateway_info["rssi"]
        end_time = entry["end_time"]

        sim.current_time = end_time
        server.receive(
            event_id,
            node.id,
            best_gateway,
            rssi,
            end_time=end_time,
            snir=snr,
        )

        expected = entry["expected_command"]
        if expected:
            # Ensure a downlink was scheduled for the expected RX window
            queue = server.scheduler.queue.get(node.id)
            assert queue, "A TXCONFIG command should have been scheduled"
            scheduled_time = queue[0][0]
            assert math.isclose(
                scheduled_time,
                expected["downlink_time"],
                rel_tol=0.0,
                abs_tol=1e-6,
            )
            frame, gateway = server.scheduler.pop_ready(
                node.id, expected["downlink_time"] + 1e-6
            )
            assert frame is not None, "The downlink frame must be ready"
            assert gateway.id == expected["gateway_id"]

            req = LinkADRReq.from_bytes(frame.payload[:5])
            decided_sf = DR_TO_SF[req.datarate]
            decided_power = TX_POWER_INDEX_TO_DBM[req.tx_power]

            assert decided_sf == expected["sf"]
            assert decided_power == expected["tx_power"]

            # Apply the downlink to the node to update SF/power for the next steps
            node.handle_downlink(frame)
            last_expected_sf = decided_sf
            last_expected_power = decided_power
        else:
            # No command should remain pending in this case
            assert not server.scheduler.queue.get(node.id)

    assert node.sf == last_expected_sf
    assert node.tx_power == last_expected_power
