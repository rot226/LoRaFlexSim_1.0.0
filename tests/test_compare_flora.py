import pytest
from pathlib import Path

from simulateur_lora_sfrd.launcher.simulator import Simulator
from simulateur_lora_sfrd.launcher.compare_flora import (
    compare_with_sim,
    load_flora_metrics,
    load_flora_rx_stats,
)


def test_compare_with_flora(tmp_path):
    pytest.importorskip('pandas')
    data_path = Path(__file__).parent / 'data' / 'flora_metrics.csv'
    flora_copy = tmp_path / 'flora_metrics.csv'
    flora_copy.write_bytes(data_path.read_bytes())

    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode='Periodic',
        packet_interval=1.0,
        packets_to_send=10,
        mobility=False,
        fixed_sf=7,
        seed=0,
    )
    sim.run()
    metrics = sim.get_metrics()
    assert compare_with_sim(metrics, flora_copy, pdr_tol=0.01)


def test_load_flora_metrics_from_sca(tmp_path):
    """Metrics should be correctly parsed from a single .sca file."""
    pytest.importorskip('pandas')
    sca = tmp_path / "metrics.sca"
    sca.write_text("""\
scalar sim sent 10
scalar sim received 8
scalar sim sf7 5
scalar sim sf8 3
""")

    metrics = load_flora_metrics(sca)
    assert metrics["PDR"] == pytest.approx(0.8)
    assert metrics["sf_distribution"] == {7: 5, 8: 3}


def test_load_flora_metrics_directory(tmp_path):
    """Aggregated metrics from a directory of .sca files are combined."""
    pytest.importorskip('pandas')
    sca1 = tmp_path / "run1.sca"
    sca1.write_text("""\
scalar sim sent 5
scalar sim received 3
scalar sim sf7 1
scalar sim sf8 4
""")
    sca2 = tmp_path / "run2.sca"
    sca2.write_text("""\
scalar sim sent 5
scalar sim received 4
scalar sim sf7 2
scalar sim sf8 3
""")

    metrics = load_flora_metrics(tmp_path)
    assert metrics["PDR"] == pytest.approx(0.7)
    assert metrics["sf_distribution"] == {7: 3, 8: 7}


def test_compare_with_flora_mismatch(tmp_path):
    """Comparison should fail when metrics differ significantly."""
    pytest.importorskip('pandas')
    data_path = Path(__file__).parent / 'data' / 'flora_metrics.csv'
    flora_copy = tmp_path / 'flora_metrics.csv'
    flora_copy.write_bytes(data_path.read_bytes())

    wrong_metrics = {"PDR": 0.0, "sf_distribution": {7: 0}}
    assert not compare_with_sim(wrong_metrics, flora_copy, pdr_tol=0.01)


def test_rssi_snr_match(tmp_path):
    """Parsed RSSI/SNR values should match simulator results."""
    pytest.importorskip('pandas')
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=1,
        mobility=False,
        fixed_sf=7,
        seed=0,
    )
    sim.run()
    df = sim.get_events_dataframe()
    rssi = float(df["rssi_dBm"].dropna().mean())
    snr = float(df["snr_dB"].dropna().mean())
    sca = tmp_path / "run.sca"
    sca.write_text(
        f"scalar sim sent 1\nscalar sim received 1\nscalar sim rssi {rssi}\nscalar sim snr {snr}\n"
    )
    stats = load_flora_rx_stats(sca)
    assert stats["rssi"] == pytest.approx(rssi)
    assert stats["snr"] == pytest.approx(snr)


def test_energy_consumption_match(tmp_path):
    """Total energy parsed from a .sca file should match simulator metrics."""
    pytest.importorskip('pandas')
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=1,
        mobility=False,
        fixed_sf=7,
        seed=0,
    )
    sim.run()
    metrics = sim.get_metrics()
    energy = metrics["energy_J"]
    sca = tmp_path / "run.sca"
    sca.write_text(
        f"scalar sim sent 1\nscalar sim received 1\nscalar sim sf7 1\nscalar sim energy_J {energy}\n"
    )
    flora_metrics = load_flora_metrics(sca)
    diff = abs(flora_metrics["energy_J"] - energy)
    assert diff / energy <= 0.05


def test_average_delay_match(tmp_path):
    """Average delay parsed from a .sca file should match simulator metrics."""
    pytest.importorskip('pandas')
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=1,
        mobility=False,
        fixed_sf=7,
        seed=0,
    )
    sim.run()
    metrics = sim.get_metrics()
    avg_delay = metrics["avg_delay_s"]
    sca = tmp_path / "run.sca"
    sca.write_text(
        f"scalar sim sent 1\nscalar sim received 1\nscalar sim sf7 1\nscalar sim avg_delay_s {avg_delay}\n"
    )
    flora_metrics = load_flora_metrics(sca)
    diff = abs(flora_metrics["avg_delay_s"] - avg_delay)
    assert diff / avg_delay <= 0.05 if avg_delay else diff == 0


def test_flora_full_mode(tmp_path):
    """PDR and SF distribution should match FLoRa within 1%."""
    pytest.importorskip('pandas')
    data_path = Path(__file__).parent / 'data' / 'flora_metrics.csv'
    flora_copy = tmp_path / 'flora_metrics.csv'
    flora_copy.write_bytes(data_path.read_bytes())

    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode='Periodic',
        packet_interval=1.0,
        packets_to_send=10,
        mobility=False,
        fixed_sf=7,
        seed=0,
        phy_model="flora_full",
    )
    sim.run()
    metrics = sim.get_metrics()
    flora = load_flora_metrics(flora_copy)
    assert abs(metrics["PDR"] - flora["PDR"]) <= 0.01
    total = sum(flora["sf_distribution"].values())
    for sf, expected in flora["sf_distribution"].items():
        got = metrics["sf_distribution"].get(sf, 0)
        assert abs(got - expected) / total <= 0.01
