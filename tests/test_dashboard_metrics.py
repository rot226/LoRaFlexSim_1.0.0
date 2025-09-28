"""Tests unitaires pour l'agrégation des métriques du tableau de bord."""

from pathlib import Path
from types import SimpleNamespace
import ast
import importlib

import pytest


def _load_aggregate_function():
    dashboard_path = (
        Path(__file__).resolve().parents[1] / "loraflexsim" / "launcher" / "dashboard.py"
    )
    source = dashboard_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    func_source = None
    for node in module_ast.body:
        if isinstance(node, ast.FunctionDef) and node.name == "aggregate_run_metrics":
            func_source = ast.get_source_segment(source, node)
            break
    if func_source is None:
        raise AssertionError("aggregate_run_metrics introuvable dans dashboard.py")
    namespace: dict = {}
    exec(func_source, namespace)
    return namespace["aggregate_run_metrics"]


aggregate_run_metrics = _load_aggregate_function()


def test_aggregate_run_metrics_weighted_values():
    metrics_runs = [
        {
            "tx_attempted": 10,
            "delivered": 9,
            "collisions": 1,
            "retransmissions": 2,
            "duplicates": 0,
            "energy_J": 1.5,
            "energy_nodes_J": 1.0,
            "energy_gateways_J": 0.5,
            "avg_delay_s": 2.0,
            "avg_arrival_interval_s": 5.0,
            "throughput_bps": 100.0,
            "simulation_time_s": 10.0,
            "energy_class_A_J": 1.0,
        },
        {
            "tx_attempted": 1000,
            "delivered": 500,
            "collisions": 500,
            "retransmissions": 50,
            "duplicates": 1,
            "energy_J": 100.0,
            "energy_nodes_J": 60.0,
            "energy_gateways_J": 40.0,
            "avg_delay_s": 10.0,
            "avg_arrival_interval_s": 7.0,
            "throughput_bps": 5.0,
            "simulation_time_s": 100.0,
            "energy_class_A_J": 30.0,
        },
    ]

    aggregated = aggregate_run_metrics(metrics_runs)

    assert aggregated["tx_attempted"] == 1010
    assert aggregated["delivered"] == 509
    assert aggregated["collisions"] == 501
    assert aggregated["retransmissions"] == 52
    assert aggregated["duplicates"] == 1
    assert aggregated["energy_J"] == 101.5
    assert aggregated["energy_nodes_J"] == 61.0
    assert aggregated["energy_gateways_J"] == 40.5
    assert aggregated["simulation_time_s"] == 110.0
    assert aggregated["energy_class_A_J"] == 31.0

    # PDR doit correspondre au rapport global entre livraisons et tentatives.
    expected_pdr = 509 / 1010
    assert aggregated["PDR"] == expected_pdr

    # Le délai moyen est pondéré par le nombre de paquets livrés.
    expected_delay = (2.0 * 9 + 10.0 * 500) / 509
    assert aggregated["avg_delay_s"] == expected_delay

    # L'intervalle d'émission moyen est pondéré par les tentatives.
    expected_interval = (5.0 * 10 + 7.0 * 1000) / 1010
    assert aggregated["avg_arrival_interval_s"] == expected_interval

    # Le débit agrégé doit être pondéré par la durée simulée.
    expected_throughput = (100.0 * 10.0 + 5.0 * 100.0) / 110.0
    assert aggregated["throughput_bps"] == expected_throughput


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_step_simulation_deduplicates_metrics_snapshots(monkeypatch):
    """Vérifie que la timeline n'accumule pas plusieurs fois le même snapshot."""

    dashboard_test_module = importlib.import_module("tests.test_dashboard_step")
    dashboard = dashboard_test_module.dashboard

    class _DummySimulator:
        def __init__(self):
            self._snapshots = [
                {"time_s": 1.0, "tx_attempted": 10, "delivered": 5},
                {"time_s": 1.0, "tx_attempted": 10, "delivered": 5},
            ]
            self._step_calls = 0
            self.running = True

        def step(self):
            self._step_calls += 1
            return True

        def get_metrics(self):
            return {
                "PDR": 0.5,
                "collisions": 0,
                "energy_J": 0.0,
                "instant_avg_delay_s": 0.0,
                "instant_throughput_bps": 0.0,
                "retransmissions": 0,
                "pdr_by_node": {0: 1.0},
                "recent_pdr_by_node": {0: 1.0},
            }

        def get_latest_metrics_snapshot(self):
            index = min(self._step_calls, len(self._snapshots)) - 1
            if index < 0:
                return None
            return dict(self._snapshots[index])

        def get_metrics_timeline(self):
            return [dict(snap) for snap in self._snapshots[: self._step_calls]]

    updates: list[tuple] = []

    monkeypatch.setattr(dashboard, "sim", _DummySimulator())
    monkeypatch.setattr(dashboard, "current_run", 1)
    monkeypatch.setattr(dashboard, "runs_metrics_timeline", [None])
    monkeypatch.setattr(dashboard, "metrics_timeline_buffer", [])
    monkeypatch.setattr(dashboard, "metrics_timeline_last_key", None)
    monkeypatch.setattr(dashboard, "_metrics_timeline_steps_since_refresh", 0)
    monkeypatch.setattr(dashboard, "session_alive", lambda *_, **__: True)
    monkeypatch.setattr(dashboard, "_set_metric_indicators", lambda *_: None)
    monkeypatch.setattr(dashboard, "update_histogram", lambda *_: None)
    monkeypatch.setattr(dashboard, "update_map", lambda: None)
    monkeypatch.setattr(dashboard, "update_timeline", lambda: None)
    monkeypatch.setattr(
        dashboard,
        "metrics_timeline_pane",
        SimpleNamespace(object=dashboard.go.Figure()),
    )
    monkeypatch.setattr(dashboard, "pdr_table", SimpleNamespace(object=None))

    def _record_update(*args, **kwargs):
        updates.append((args, kwargs))

    monkeypatch.setattr(dashboard, "_update_metrics_timeline_pane", _record_update)

    dashboard.step_simulation()
    dashboard.step_simulation()

    run_timeline = dashboard.runs_metrics_timeline[dashboard.current_run - 1]

    assert isinstance(run_timeline, list)
    assert len(run_timeline) == 1
    assert len(dashboard.metrics_timeline_buffer) == 1
    assert len(updates) == 1
    assert dashboard._metrics_timeline_steps_since_refresh == 1
