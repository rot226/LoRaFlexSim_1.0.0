import subprocess
import pytest

try:
    pn = pytest.importorskip("panel")
    pd = pytest.importorskip("pandas")
except Exception:
    pytest.skip("panel or pandas import failed", allow_module_level=True)

from loraflexsim.launcher import dashboard  # noqa: E402


def test_export_to_tmp_dir(tmp_path, monkeypatch):
    df = pd.DataFrame({"a": [1], "b": [2]})
    dashboard.runs_events = [df]
    dashboard.runs_metrics = [{"PDR": 100}]
    dashboard.runs_metrics_timeline = [
        pd.DataFrame(
            {
                "time_s": [0.5],
                "PDR": [1.0],
                "tx_attempted": [1],
                "delivered": [1],
                "collisions": [0],
                "instant_throughput_bps": [160.0],
            }
        )
    ]
    dashboard.export_message = pn.pane.Markdown()
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)
    dashboard.exporter_csv()
    files = sorted(tmp_path.glob("*.csv"))
    assert len(files) == 3
