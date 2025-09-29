import subprocess
import pytest

try:
    pn = pytest.importorskip("panel")
    pd = pytest.importorskip("pandas")
except Exception:
    pytest.skip("panel or pandas import failed", allow_module_level=True)

from loraflexsim.launcher import dashboard  # noqa: E402
from loraflexsim.launcher.simulator import Simulator  # noqa: E402


def test_export_to_tmp_dir(tmp_path, monkeypatch):
    df = pd.DataFrame({"a": [1], "b": [2]})
    dashboard.runs_events = [df]
    dashboard.runs_metrics = [{"PDR": 100}]
    dashboard.export_message = pn.pane.Markdown()
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)
    dashboard.exporter_csv()
    files = sorted(tmp_path.glob("*.csv"))
    assert len(files) == 2
    assert any("metrics_" in file.name for file in files)


def test_exporter_csv_includes_delayed_metrics(tmp_path, monkeypatch):
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        packets_to_send=1,
        duty_cycle=None,
        mobility=False,
        flora_mode=True,
        flora_timing=True,
        area_size=10.0,
        seed=777,
    )
    if sim.nodes and sim.gateways:
        node = sim.nodes[0]
        gateway = sim.gateways[0]
        node.x = node.y = 0.0
        node.initial_x = node.initial_y = 0.0
        gateway.x = gateway.y = 0.0
    sim.run()

    events_df = pd.DataFrame(sim.events_log)
    metrics = sim.get_metrics()
    dashboard.runs_events = [events_df]
    dashboard.runs_metrics = [metrics]
    markdown_cls = getattr(pn.pane, "Markdown", pn.pane.HTML)
    dashboard.export_message = markdown_cls()

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: None)
    monkeypatch.chdir(tmp_path)

    dashboard.exporter_csv()

    metrics_files = sorted(tmp_path.glob("metrics_*.csv"))
    timeline_files = sorted(tmp_path.glob("metrics_timeline_*.csv"))
    assert metrics_files
    assert not timeline_files

    metrics_df = pd.read_csv(metrics_files[-1])

    throughput_values = [value for value in metrics_df["instant_throughput_bps"] if value is not None]
    delay_values = [value for value in metrics_df["instant_avg_delay_s"] if value is not None]
    assert any(value > 0 for value in throughput_values)
    assert any(value > 0 for value in delay_values)
