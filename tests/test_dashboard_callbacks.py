"""Tests pour les callbacks du tableau de bord Panel."""

from collections import deque

import pytest

from tests.test_dashboard_step import _install_panel_stub, _install_pandas_stub


_install_panel_stub()
_install_pandas_stub()


class _DummyTable:
    def __init__(self):
        self.object = None


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_step_simulation_skips_map_updates_without_snapshot(monkeypatch):
    """Vérifie que la carte et la timeline ne sont rafraîchies que sur nouveau snapshot."""

    from loraflexsim.launcher import dashboard

    class _DummySim:
        def __init__(self):
            self.step_calls = 0
            self.running = True
            self.events_log = []
            self.nodes = []
            self.gateways = []
            self.current_time = 0.0

        def step(self):
            self.step_calls += 1
            return True

        def get_metrics(self):
            return {
                "PDR": 1.0,
                "collisions": 0,
                "energy_J": 0.0,
                "instant_avg_delay_s": 0.0,
                "instant_throughput_bps": 0.0,
                "retransmissions": 0,
                "pdr_by_node": {0: 1.0},
                "recent_pdr_by_node": {0: 1.0},
            }

        def get_latest_metrics_snapshot(self):
            if self.step_calls == 0:
                return None
            return {"time_s": 0.0, "tx_attempted": 1, "delivered": 1}

        def get_metrics_timeline(self):
            return []

    dummy_sim = _DummySim()

    monkeypatch.setattr(dashboard, "sim", dummy_sim)
    monkeypatch.setattr(dashboard, "session_alive", lambda *_, **__: True)
    monkeypatch.setattr(dashboard, "update_histogram", lambda *_: None)
    monkeypatch.setattr(dashboard, "_set_metric_indicators", lambda *_: None)
    monkeypatch.setattr(dashboard, "_update_metrics_timeline_pane", lambda *_: None)
    monkeypatch.setattr(dashboard, "pdr_table", _DummyTable())

    dashboard.metrics_timeline_buffer = []
    dashboard.metrics_timeline_window = deque(
        maxlen=dashboard.METRICS_TIMELINE_WINDOW_SIZE
    )
    dashboard.metrics_timeline_last_key = None
    dashboard._metrics_timeline_steps_since_refresh = 0
    dashboard.current_run = 0
    dashboard.runs_metrics_timeline = []

    calls = {"map": 0, "timeline": 0}

    def _inc_map():
        calls["map"] += 1

    def _inc_timeline():
        calls["timeline"] += 1

    monkeypatch.setattr(dashboard, "update_map", _inc_map)
    monkeypatch.setattr(dashboard, "update_timeline", _inc_timeline)

    dashboard.step_simulation()
    assert calls == {"map": 1, "timeline": 1}

    dashboard.step_simulation()
    assert calls == {"map": 1, "timeline": 1}

    dashboard.step_simulation()
    assert calls == {"map": 1, "timeline": 1}
