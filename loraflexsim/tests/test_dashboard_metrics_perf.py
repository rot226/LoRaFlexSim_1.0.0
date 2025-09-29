import math
from collections import deque

import pytest

from loraflexsim.launcher import dashboard


class _FakeSim:
    def __init__(self, timeline):
        self.timeline = timeline
        self.step_calls = 0
        self.get_metrics_calls = 0
        self.running = True
        self.num_nodes = 1
        self.events_log = []
        self.current_time = timeline[-1]["time_s"] if timeline else 0.0

    def step(self):
        self.step_calls += 1
        return True

    def get_latest_metrics_snapshot(self):
        if self.step_calls == 0:
            return None
        if self.step_calls == 1:
            return dict(self.timeline[-1]) if self.timeline else None
        if self.step_calls == 2 and self.timeline:
            base = dict(self.timeline[-1])
            base["time_s"] = float(base.get("time_s", 0.0)) + 1.0
            base["tx_attempted"] = float(base.get("tx_attempted", 0.0)) + 1.0
            base["delivered"] = float(base.get("delivered", 0.0)) + 1.0
            base.setdefault("retransmissions", float(base.get("retransmissions", 0.0)))
            return base
        return dict(self.timeline[-1]) if self.timeline else None

    def get_metrics(self):
        self.get_metrics_calls += 1
        return {
            "PDR": 0.5,
            "collisions": 0.0,
            "energy_J": 0.0,
            "instant_avg_delay_s": 0.0,
            "instant_throughput_bps": 0.0,
            "throughput_bps": 0.0,
            "avg_delay_s": 0.0,
            "pdr_by_node": {1: 0.5},
            "recent_pdr_by_node": {1: 0.5},
            "sf_distribution": {7: 1},
            "retransmissions": 0.0,
        }

    def get_metrics_timeline(self):
        return self.timeline


@pytest.fixture
def large_timeline():
    window = dashboard.METRICS_TIMELINE_WINDOW_SIZE
    size = window + 20
    records: list[dict[str, float]] = []
    for idx in range(size):
        records.append(
            {
                "time_s": float(idx),
                "PDR": 0.5,
                "tx_attempted": float(idx + 1),
                "delivered": float(idx),
                "collisions": 0.0,
                "duplicates": 0.0,
                "packets_lost_no_signal": 0.0,
                "energy_J": 0.0,
                "instant_throughput_bps": 0.0,
                "avg_delay_s": 0.0,
                "instant_avg_delay_s": 0.0,
                "total_delay_s": float(idx),
                "delivered_count": float(idx),
                "losses_total": 1.0,
                "recent_losses": 1.0,
                "retransmissions": 0.0,
            }
        )
    return records


def test_step_simulation_skips_expensive_refresh(monkeypatch, large_timeline):
    dashboard.sim = None
    dashboard.current_run = 0
    dashboard.runs_metrics_timeline = []
    dashboard.metrics_timeline_buffer = large_timeline
    dashboard.metrics_timeline_window = deque(
        large_timeline[-dashboard.METRICS_TIMELINE_WINDOW_SIZE :],
        maxlen=dashboard.METRICS_TIMELINE_WINDOW_SIZE,
    )
    dashboard.metrics_timeline_last_key = dashboard._snapshot_signature(
        large_timeline[-1]
    )
    dashboard._metrics_timeline_steps_since_refresh = 0

    dashboard.metrics_timeline_pane.object = dashboard._create_empty_metrics_timeline_figure()
    dashboard._update_metrics_timeline_pane(large_timeline, force=True)
    initial_fig = dashboard.metrics_timeline_pane.object
    initial_trace_lengths = [len(trace.x) if trace.x is not None else 0 for trace in initial_fig.data]
    initial_table = dashboard.pdr_table.object

    fake_sim = _FakeSim(large_timeline)
    monkeypatch.setattr(dashboard, "session_alive", lambda *_, **__: True)
    monkeypatch.setattr(dashboard, "update_map", lambda: None)
    monkeypatch.setattr(dashboard, "update_timeline", lambda: None)

    histogram_calls: list[dict | None] = []

    def record_histogram(metrics=None):
        histogram_calls.append(metrics)

    monkeypatch.setattr(dashboard, "update_histogram", record_histogram)

    set_window_calls = {"count": 0}
    original_set_window = dashboard._set_metrics_timeline_window

    def tracking_set_window(timeline):
        set_window_calls["count"] += 1
        return original_set_window(timeline)

    monkeypatch.setattr(dashboard, "_set_metrics_timeline_window", tracking_set_window)

    update_calls = {"append": 0, "force": 0}
    original_update = dashboard._update_metrics_timeline_pane

    def tracking_update(timeline, latest_snapshot=None, *, append=False, force=False):
        if append:
            update_calls["append"] += 1
        if force:
            update_calls["force"] += 1
        return original_update(timeline, latest_snapshot, append=append, force=force)

    monkeypatch.setattr(dashboard, "_update_metrics_timeline_pane", tracking_update)

    dashboard.sim = fake_sim

    dashboard.step_simulation()

    assert fake_sim.get_metrics_calls == 0
    assert set_window_calls["count"] == 0
    assert histogram_calls == []
    assert dashboard.metrics_timeline_pane.object is initial_fig
    after_first_lengths = [len(trace.x) if trace.x is not None else 0 for trace in initial_fig.data]
    assert after_first_lengths == initial_trace_lengths
    assert dashboard.pdr_table.object is initial_table

    previous_last_time = large_timeline[-1]["time_s"]

    dashboard.step_simulation()

    assert fake_sim.get_metrics_calls == 1
    assert len(histogram_calls) == 1
    assert set_window_calls["count"] == 0
    assert update_calls["append"] == 1
    expected_time = previous_last_time + 1.0
    assert math.isclose(large_timeline[-1]["time_s"], expected_time)
    assert math.isclose(dashboard.metrics_timeline_window[-1]["time_s"], expected_time)
    last_trace = initial_fig.data[0]
    assert math.isclose(last_trace.x[-1], expected_time)

    dashboard.sim = None
    dashboard.metrics_timeline_buffer = []
    dashboard.metrics_timeline_window = deque(
        maxlen=dashboard.METRICS_TIMELINE_WINDOW_SIZE
    )
    dashboard.metrics_timeline_last_key = None
    dashboard._metrics_timeline_steps_since_refresh = 0
    dashboard.metrics_timeline_pane.object = dashboard._create_empty_metrics_timeline_figure()
