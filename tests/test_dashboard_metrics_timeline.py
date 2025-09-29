"""Tests ciblés pour la timeline des métriques du tableau de bord."""

from collections import deque
from types import SimpleNamespace

import pytest

from tests.test_dashboard_step import _install_panel_stub

_install_panel_stub()

import loraflexsim.launcher.dashboard as dashboard


@pytest.fixture(autouse=True)
def _reset_metrics_timeline(monkeypatch):
    """Réinitialise les structures tampon avant chaque test."""

    window = deque(maxlen=dashboard.METRICS_TIMELINE_WINDOW_SIZE)
    monkeypatch.setattr(dashboard, "metrics_timeline_window", window)
    monkeypatch.setattr(dashboard, "metrics_timeline_buffer", [])
    monkeypatch.setattr(
        dashboard,
        "metrics_timeline_pane",
        SimpleNamespace(object=None),
    )
    dashboard._metrics_timeline_steps_since_refresh = 0
    yield


def test_incremental_updates_limit_dataframe_calls(monkeypatch):
    """Vérifie que les mises à jour incrémentales évitent les reconstructions complètes."""

    to_df_calls = 0
    build_calls = 0

    original_to_df = dashboard._metrics_timeline_to_dataframe
    original_build = dashboard._build_metrics_timeline_figure

    def _count_to_df(timeline):
        nonlocal to_df_calls
        to_df_calls += 1
        return original_to_df(timeline)

    def _count_build(timeline):
        nonlocal build_calls
        build_calls += 1
        return original_build(timeline)

    monkeypatch.setattr(dashboard, "_metrics_timeline_to_dataframe", _count_to_df)
    monkeypatch.setattr(dashboard, "_build_metrics_timeline_figure", _count_build)

    window = dashboard.metrics_timeline_window

    for i in range(1000):
        snapshot = {
            "time_s": float(i),
            "PDR": 1.0 - (i % 100) / 200.0,
            "collisions": i % 5,
            "duplicates": i % 7,
            "packets_lost_no_signal": i % 11,
            "energy_J": float(i) / 10.0,
            "instant_throughput_bps": float(i) * 8.0,
        }
        window.append(snapshot)
        if i == 0:
            dashboard._update_metrics_timeline_pane(window)
        else:
            dashboard._update_metrics_timeline_pane(
                window, latest_snapshot=snapshot, append=True
            )

    fig = dashboard.metrics_timeline_pane.object
    assert isinstance(fig, dashboard.go.Figure)
    assert to_df_calls <= 3  # initialisation + rafraîchissements éventuels limités
    assert build_calls == 0

    expected_length = min(1000, dashboard.METRICS_TIMELINE_WINDOW_SIZE)
    for trace in fig.data:
        assert len(trace.x) == expected_length
        assert len(trace.y) == expected_length

    # La fenêtre doit contenir uniquement les derniers points.
    assert len(window) == expected_length
    first_time = fig.data[0].x[0]
    last_time = fig.data[0].x[-1]
    assert last_time - first_time <= dashboard.METRICS_TIMELINE_WINDOW_SIZE
