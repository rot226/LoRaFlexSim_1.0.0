import importlib
from types import SimpleNamespace

class DummyButton:
    def __init__(self, disabled=False):
        self.disabled = disabled
        self.name = ""
        self.button_type = "primary"


class DummyProgress:
    def __init__(self):
        self.visible = False
        self.value = 0


class DummyIndicator:
    def __init__(self):
        self.value = 0


class DummyPane:
    def __init__(self):
        self.object = None


class FakeDoc:
    def __init__(self):
        self.session_context = SimpleNamespace(session=object())
        self._callbacks = []

    def add_next_tick_callback(self, callback):
        self._callbacks.append(callback)
        callback()


class DummySim:
    def __init__(self):
        self.packets_to_send = 1
        self.num_nodes = 1
        self.event_queue = [object()]
        self.running = True
        self.packets_sent = 0
        self.current_time = 0.0
        self.max_sim_time = 1.0

    def step(self):
        self.event_queue.pop()
        self.packets_sent = 1
        self.current_time = 1.0
        self.running = False

    def get_metrics(self):
        return {
            "PDR": 1.0,
            "collisions": 0,
            "energy_J": 0.0,
            "avg_delay_s": 0.0,
            "throughput_bps": 0.0,
            "retransmissions": 0,
            "sf_distribution": {7: 1},
        }


class ImmediateThread:
    def __init__(self, target, daemon=None):
        self._target = target
        self.daemon = daemon

    def start(self):
        self._target()


def test_fast_forward_worker_handles_pn_state(monkeypatch):
    dashboard = importlib.import_module("loraflexsim.launcher.dashboard")

    fake_doc = FakeDoc()
    fake_state = SimpleNamespace(curdoc=fake_doc)
    monkeypatch.setitem(dashboard._SESSION_STATE, "state", fake_state)

    class BrokenState:
        def __getattr__(self, name):  # pragma: no cover - defensive
            raise NameError("pn.state should not be used inside the worker")

    monkeypatch.setattr(dashboard, "pn", SimpleNamespace(state=BrokenState()), raising=False)

    dashboard.sim = DummySim()
    dashboard.sim_callback = None
    dashboard.map_anim_callback = None
    dashboard.chrono_callback = None
    dashboard.paused = False
    dashboard.pause_prev_disabled = False

    dashboard.fast_forward_button = DummyButton(disabled=False)
    dashboard.stop_button = DummyButton(disabled=False)
    dashboard.pause_button = DummyButton(disabled=False)
    dashboard.export_button = DummyButton(disabled=False)
    dashboard.fast_forward_progress = DummyProgress()
    dashboard.export_message = SimpleNamespace(object="")

    dashboard.pdr_indicator = DummyIndicator()
    dashboard.collisions_indicator = DummyIndicator()
    dashboard.energy_indicator = DummyIndicator()
    dashboard.delay_indicator = DummyIndicator()
    dashboard.throughput_indicator = DummyIndicator()
    dashboard.retrans_indicator = DummyIndicator()
    dashboard.sf_hist_pane = DummyPane()

    monkeypatch.setattr(dashboard, "update_map", lambda: None)
    monkeypatch.setattr(dashboard, "_cleanup_callbacks", lambda: None)

    stop_calls = []

    def fake_on_stop(event):
        stop_calls.append(event)

    monkeypatch.setattr(dashboard, "on_stop", fake_on_stop)
    monkeypatch.setattr(dashboard.threading, "Thread", ImmediateThread)

    dashboard.fast_forward()

    # The worker should have run without relying on the monkeypatched pn.state
    assert dashboard.fast_forward_progress.value == 100
    assert dashboard.fast_forward_progress.visible is False
    assert dashboard.export_button.disabled is False
    assert dashboard.pause_button.disabled is False
    assert dashboard.stop_button.disabled is True
    assert dashboard.fast_forward_button.disabled is True
    assert stop_calls, "on_stop should be invoked to finalise the run"
    assert not dashboard.sim.running
