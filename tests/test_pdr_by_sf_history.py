from collections import Counter

import pytest

from loraflexsim.launcher.adr_standard_1 import apply as apply_adr
from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher.simulator import Simulator


def test_pdr_by_sf_tracks_actual_history():
    """Le PDR par SF doit refléter l'historique même après un changement ADR."""
    channel = Channel(shadowing_std=0.0, fast_fading_std=0.0, noise_floor_std=0.0)
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=30,
        mobility=False,
        adr_server=True,
        adr_method="avg",
        channels=[channel],
        seed=1,
    )
    apply_adr(sim)
    node = sim.nodes[0]
    gateway = sim.gateways[0]
    node.x = 0.0
    node.y = 0.0
    gateway.x = 1.0
    gateway.y = 0.0
    initial_sf = node.sf

    sim.run()

    # Vérifier qu'un changement de SF a bien eu lieu via ADR
    assert node.sf != initial_sf

    metrics = sim.get_metrics()
    pdr_by_sf = metrics["pdr_by_sf"]

    attempts = Counter()
    success = Counter()
    for entry in sim.events_log:
        if entry.get("result") in {"Success", "CollisionLoss", "NoCoverage"}:
            sf = entry.get("sf")
            attempts[sf] += 1
            if entry["result"] == "Success":
                success[sf] += 1

    # Les SF réellement utilisés doivent être présents dans les métriques
    observed_sfs = {sf for sf, count in attempts.items() if count > 0}
    assert observed_sfs <= set(pdr_by_sf.keys())
    assert len(observed_sfs) >= 2

    for sf in observed_sfs:
        ratio = success[sf] / attempts[sf]
        assert pdr_by_sf[sf] == pytest.approx(ratio)
