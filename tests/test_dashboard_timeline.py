"""Tests spécifiques à la timeline du tableau de bord."""

from __future__ import annotations

import math

import pytest

from loraflexsim.launcher import dashboard


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_update_timeline_maintains_persistent_traces(monkeypatch):
    """Injection massive d'événements sans explosion du nombre de traces."""

    monkeypatch.setattr(
        dashboard, "session_alive", lambda doc=None, state_container=None: True
    )

    class DummySim:
        def __init__(self, events):
            self.events_log = events
            self.current_time = events[-1]["end_time"] if events else 0.0

    events: list[dict[str, float | int | str]] = []
    for i in range(1000):
        start = float(i) * 0.1
        end = start + 0.05
        result = "Success" if i < 999 else "Failure"
        events.append(
            {
                "node_id": i % 7,
                "start_time": start,
                "end_time": end,
                "result": result,
            }
        )

    original_sim = dashboard.sim
    try:
        dashboard.sim = DummySim(events)
        dashboard.timeline_fig = dashboard.go.Figure()
        dashboard.timeline_success_segments.clear()
        dashboard.timeline_failure_segments.clear()
        dashboard.timeline_pane.object = dashboard.timeline_fig
        dashboard.last_event_index = 0

        dashboard.update_timeline()

        assert len(dashboard.timeline_fig.data) == 2

        expected_success_segments = [
            (float(ev["start_time"]), float(ev["end_time"]), int(ev["node_id"]))
            for ev in events
            if ev["result"] == "Success"
        ][-dashboard._TIMELINE_MAX_SEGMENTS :]
        expected_failure_segments = [
            (float(ev["start_time"]), float(ev["end_time"]), int(ev["node_id"]))
            for ev in events
            if ev["result"] != "Success"
        ][-dashboard._TIMELINE_MAX_SEGMENTS :]

        assert list(dashboard.timeline_success_segments) == expected_success_segments
        assert list(dashboard.timeline_failure_segments) == expected_failure_segments

        success_trace = next(
            trace for trace in dashboard.timeline_fig.data if trace.name == "Succès"
        )
        failure_trace = next(
            trace for trace in dashboard.timeline_fig.data if trace.name == "Échecs"
        )

        def _flatten(segments: list[tuple[float, float, int]]):
            x_values: list[float | None] = []
            y_values: list[int | None] = []
            for start, end, node in segments:
                x_values.extend((start, end, None))
                y_values.extend((node, node, None))
            return x_values, y_values

        exp_success_x, exp_success_y = _flatten(expected_success_segments)
        exp_failure_x, exp_failure_y = _flatten(expected_failure_segments)

        assert list(success_trace.x) == exp_success_x
        assert list(success_trace.y) == exp_success_y
        assert list(failure_trace.x) == exp_failure_x
        assert list(failure_trace.y) == exp_failure_y

        assert math.isclose(
            success_trace.x[-2], events[-2]["end_time"], rel_tol=1e-9, abs_tol=1e-9
        )
        assert math.isclose(
            failure_trace.x[-2], events[-1]["end_time"], rel_tol=1e-9, abs_tol=1e-9
        )

        assert dashboard.last_event_index == len(events)
        assert dashboard.timeline_pane.object is dashboard.timeline_fig
    finally:
        dashboard.sim = original_sim
        dashboard.timeline_success_segments.clear()
        dashboard.timeline_failure_segments.clear()
        dashboard.timeline_fig = dashboard.go.Figure()
        dashboard.timeline_pane.object = dashboard.timeline_fig
        dashboard.last_event_index = 0
