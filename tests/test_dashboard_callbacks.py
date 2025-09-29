"""Tests pour les callbacks du tableau de bord Panel."""

import pytest

from tests.test_dashboard_step import _install_panel_stub, _install_pandas_stub


_install_panel_stub()
_install_pandas_stub()


class _DummyTable:
    def __init__(self):
        self.object = None


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_step_simulation_updates_map_and_limits_metric_fetches(monkeypatch):
    """Vérifie que ``step_simulation`` met la carte à jour tout en évitant des calculs inutiles."""

    from loraflexsim.launcher import dashboard

    class _DummySim:
        def __init__(self):
            self.step_calls = 0
            self.metrics_calls = 0
            self.running = True
            self.events_log = []
            self.nodes = []
            self.gateways = []
            self.current_time = 0.0
            self.tx_attempted = 0
            self.rx_delivered = 0

        def step(self):
            self.step_calls += 1
            if self.step_calls == 1:
                self.tx_attempted = 1
                self.rx_delivered = 1
            return self.step_calls < 3

        def get_metrics(self):
            self.metrics_calls += 1
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
            return {
                "time_s": float(self.step_calls),
                "tx_attempted": float(self.tx_attempted),
                "delivered": float(self.rx_delivered),
            }

    dummy_sim = _DummySim()

    monkeypatch.setattr(dashboard, "sim", dummy_sim)
    monkeypatch.setattr(dashboard, "session_alive", lambda *_, **__: True)
    monkeypatch.setattr(dashboard, "update_histogram", lambda *_: None)
    monkeypatch.setattr(dashboard, "_set_metric_indicators", lambda *_: None)
    monkeypatch.setattr(dashboard, "pdr_table", _DummyTable())
    monkeypatch.setattr(dashboard, "on_stop", lambda *_: None)

    map_calls = 0

    def _inc_map():
        nonlocal map_calls
        map_calls += 1

    monkeypatch.setattr(dashboard, "update_map", _inc_map)

    dashboard.step_simulation()
    dashboard.step_simulation()
    dashboard.step_simulation()

    assert map_calls == 3
    assert dummy_sim.metrics_calls == 1
