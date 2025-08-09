from pathlib import Path

import pytest

from simulateur_lora_sfrd.launcher.adr_standard_1 import apply as adr1
from simulateur_lora_sfrd.launcher.compare_flora import (
    compare_with_sim,
    load_flora_metrics,
    load_flora_rx_stats,
)
from simulateur_lora_sfrd.launcher import Simulator

CONFIG = "flora-master/simulations/examples/n100-gw1.ini"

@pytest.mark.slow
def test_flora_sca_compare():
    pytest.importorskip("pandas")
    sca = Path(__file__).parent / "data" / "n100_gw1_expected.sca"
    sim = Simulator(flora_mode=True, config_file=CONFIG, seed=1, adr_method="avg")
    adr1(sim)
    sim.run(1000)
    metrics = sim.get_metrics()

    load_flora_metrics(sca)
    load_flora_rx_stats(sca)  # ensure parser works

    assert compare_with_sim(metrics, sca, pdr_tol=0.01)
