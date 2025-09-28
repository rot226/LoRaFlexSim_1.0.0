from pathlib import Path

import pytest

try:
    pytest.importorskip("pandas")
except Exception:
    pytest.skip("pandas import failed", allow_module_level=True)

from loraflexsim.launcher.adr_standard_1 import apply as adr1
from loraflexsim.launcher.compare_flora import (
    compare_with_sim,
    load_flora_metrics,
    load_flora_rx_stats,
)
from loraflexsim.launcher import Simulator

CONFIG = "flora-master/simulations/examples/n100-gw1.ini"

@pytest.mark.slow
def test_flora_sca_compare():
    sca = Path(__file__).parent / "data" / "n100_gw1_expected.sca"
    sim = Simulator(flora_mode=True, config_file=CONFIG, seed=1, adr_method="avg")
    adr1(sim)
    sim.run(1000)
    metrics = sim.get_metrics()

    load_flora_metrics(sca)
    flora_rx = load_flora_rx_stats(sca)

    assert compare_with_sim(metrics, sca, pdr_tol=0.01)
    snr_values = [snr for snr in sim.network_server.event_snir.values() if snr is not None]
    assert snr_values, "aucune mesure SNR enregistrée"
    avg_snr = sum(snr_values) / len(snr_values)
    assert abs(avg_snr - flora_rx["snr"]) <= 0.5


@pytest.mark.slow
def test_flora_sca_quantization_trace():
    sim = Simulator(flora_mode=True, config_file=CONFIG, seed=1, adr_method="avg")
    adr1(sim)
    sim.run(1000)
    sim_q = Simulator(
        flora_mode=True, config_file=CONFIG, seed=1, adr_method="avg", tick_ns=1
    )
    adr1(sim_q)
    sim_q.run(1000)

    def to_ns(log_map):
        return [
            (
                int(round(e["start_time"] * 1e9)),
                int(round(e["end_time"] * 1e9)),
            )
            for e in sorted(log_map.values(), key=lambda ev: ev["start_time"])
        ]

    assert to_ns(sim._events_log_map) == to_ns(sim_q._events_log_map)
