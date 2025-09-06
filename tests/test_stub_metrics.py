"""Tests ensuring simulations rely on stubbed dependencies and cleanup."""

from pathlib import Path

import numpy as np
import scipy

from loraflexsim.launcher.simulator import Simulator


TMP_FILENAME = "temp_file_cleanup_test.txt"


def test_simulation_uses_stubbed_metrics() -> None:
    """Simulator should run using stub versions of numpy and scipy."""
    assert np.__name__ == "numpy_stub"
    assert "scipy/stats.py" in Path(scipy.stats.__file__).as_posix()

    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Random",
        packet_interval=1.0,
        packets_to_send=1,
        duty_cycle=0.01,
        seed=0,
    )
    sim.run()
    metrics = sim.get_metrics()
    assert "PDR" in metrics


def test_tmp_path_cleanup(tmp_path) -> None:
    """Temporary files are removed after each test."""
    tmp_file = tmp_path / TMP_FILENAME
    tmp_file.write_text("data")
    assert tmp_file.exists()


def test_no_tmp_artifacts(tmp_path_factory) -> None:
    base = tmp_path_factory.getbasetemp()
    assert not list(base.glob(f"**/{TMP_FILENAME}"))

