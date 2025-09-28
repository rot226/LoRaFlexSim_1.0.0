from types import SimpleNamespace

import pandas as pd
import pytest

panel = pytest.importorskip("panel")
dashboard = pytest.importorskip("loraflexsim.launcher.dashboard")


def reset_inputs():
    dashboard.sim = None
    dashboard.interval_input.value = 1.0
    dashboard.num_nodes_input.value = 1
    dashboard.area_input.value = 100.0
    dashboard.packets_input.value = 1
    dashboard.real_time_duration_input.value = 0.0
    dashboard.export_message.object = ""


def test_invalid_interval_prevents_start():
    reset_inputs()
    dashboard.interval_input.value = 0
    dashboard.on_start(None)
    assert dashboard.sim is None
    assert "⚠️" in dashboard.export_message.object


def test_invalid_nodes_prevents_start():
    reset_inputs()
    dashboard.num_nodes_input.value = 0
    dashboard.on_start(None)
    assert dashboard.sim is None
    assert "⚠️" in dashboard.export_message.object


def test_invalid_area_prevents_start():
    reset_inputs()
    dashboard.area_input.value = -1
    dashboard.on_start(None)
    assert dashboard.sim is None
    assert "⚠️" in dashboard.export_message.object


def test_step_simulation_updates_metrics(monkeypatch):
    class DummySim:
        def __init__(self):
            self.step_called = False

        def step(self):
            self.step_called = True
            return True

        def get_metrics(self):
            return metrics

        def get_metrics_timeline(self):
            return timeline

    metrics = {
        "PDR": 0.75,
        "collisions": 2,
        "energy_J": 1.234,
        "avg_delay_s": 4.2,
        "throughput_bps": 12.5,
        "retransmissions": 1,
        "pdr_by_node": {"n0": 0.7, "n1": 0.8},
        "recent_pdr_by_node": {"n0": 0.6, "n1": 0.9},
    }
    timeline = [
        {"node": "n0", "start": 0.0, "end": 1.0},
        {"node": "n1", "start": 1.5, "end": 2.0},
    ]

    dummy = DummySim()

    monkeypatch.setattr(dashboard, "sim", dummy, raising=False)
    monkeypatch.setattr(dashboard, "session_alive", lambda: True)
    monkeypatch.setattr(dashboard, "current_run", 1, raising=False)
    monkeypatch.setattr(dashboard, "runs_metrics_timeline", [], raising=False)

    captured_histogram_metrics = {}
    captured_timeline_updates = {"called": 0}

    def fake_histogram(data):
        captured_histogram_metrics["metrics"] = data

    def fake_map():
        captured_timeline_updates.setdefault("map", 0)
        captured_timeline_updates["map"] += 1

    def fake_timeline():
        captured_timeline_updates["called"] += 1

    monkeypatch.setattr(dashboard, "update_histogram", fake_histogram)
    monkeypatch.setattr(dashboard, "update_map", fake_map)
    monkeypatch.setattr(dashboard, "update_timeline", fake_timeline)
    monkeypatch.setattr(dashboard, "on_stop", lambda *_: None)

    dashboard.step_simulation()

    assert dummy.step_called is True
    assert dashboard.pdr_indicator.value == pytest.approx(0.75)
    assert dashboard.energy_indicator.value == pytest.approx(1.234)
    assert captured_histogram_metrics["metrics"] is metrics
    assert captured_timeline_updates["called"] == 1

    pdr_df = dashboard.pdr_table.object
    assert isinstance(pdr_df, pd.DataFrame)
    assert list(pdr_df["Node"]) == ["n0", "n1"]
    assert list(pdr_df["PDR"]) == [0.7, 0.8]
    assert list(pdr_df["Recent PDR"]) == [0.6, 0.9]

    assert dashboard.runs_metrics_timeline[0] is timeline


def test_select_adr_does_not_enable_advanced_degradation(monkeypatch):
    class FakeModule:
        def __init__(self):
            self.calls: list[dict] = []

        def apply(self, *_args, **kwargs):
            self.calls.append(kwargs)

    fake_module = FakeModule()
    fake_sim = object()

    monkeypatch.setattr(dashboard, "sim", fake_sim, raising=False)
    monkeypatch.setattr(dashboard, "selected_adr_module", None, raising=False)
    monkeypatch.setattr(
        dashboard,
        "adr_select",
        SimpleNamespace(value=None),
    )
    monkeypatch.setattr(
        dashboard,
        "adr_node_checkbox",
        SimpleNamespace(value=False),
    )
    monkeypatch.setattr(
        dashboard,
        "adr_server_checkbox",
        SimpleNamespace(value=False),
    )

    dashboard.select_adr(fake_module, "ADR 1")

    assert fake_module.calls == [{}]
    assert dashboard.adr_select.value == "ADR 1"
    assert dashboard.adr_node_checkbox.value is True
    assert dashboard.adr_server_checkbox.value is True
