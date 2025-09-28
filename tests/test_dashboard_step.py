"""Tests pour la fonction ``step_simulation`` du tableau de bord Panel."""

import sys
import types

import numpy_stub
import pytest


def _install_panel_stub():
    """Installe un faux module :mod:`panel` suffisant pour importer le tableau de bord."""

    if "panel" in sys.modules:
        return

    class _DummyPeriodicCallback:
        def stop(self):
            pass

    class _DummyParam:
        def watch(self, *_, **__):
            return None

    class _DummyWidget:
        def __init__(self, *args, **kwargs):
            self.value = kwargs.get("value")
            self.options = kwargs.get("options")
            self.disabled = kwargs.get("disabled", False)
            self.name = kwargs.get("name", "")
            self.button_type = kwargs.get("button_type", "")
            self.param = _DummyParam()
            self.object = kwargs.get("object")
            self.visible = kwargs.get("visible", True)
            self.width = kwargs.get("width")
            self.height = kwargs.get("height")

        def on_click(self, *_args, **_kwargs):
            return None

        def servable(self, *_args, **_kwargs):
            return self

    class _DummyPane(_DummyWidget):
        pass

    class _DummyDoc:
        def __init__(self):
            self.title = ""
            self.session_context = types.SimpleNamespace(session=object())

        def __bool__(self):
            return True

    class _DummyState:
        def __init__(self):
            self.curdoc = _DummyDoc()

        def add_periodic_callback(self, *_args, **_kwargs):
            return _DummyPeriodicCallback()

        def on_session_destroyed(self, *_args, **_kwargs):
            return None

    panel_module = types.ModuleType("panel")
    panel_module.extension = lambda *_, **__: None
    panel_module.state = _DummyState()

    widgets_module = types.ModuleType("panel.widgets")
    for widget_name in [
        "IntInput",
        "FloatInput",
        "RadioButtonGroup",
        "FloatSlider",
        "IntSlider",
        "Select",
        "Checkbox",
        "Button",
        "Toggle",
        "TextAreaInput",
    ]:
        setattr(widgets_module, widget_name, _DummyWidget)

    indicators_module = types.ModuleType("panel.indicators")
    indicators_module.Number = _DummyWidget
    indicators_module.Progress = _DummyWidget

    pane_module = types.ModuleType("panel.pane")
    pane_module.HTML = _DummyPane
    pane_module.DataFrame = _DummyPane
    pane_module.Plotly = _DummyPane

    panel_module.widgets = widgets_module
    panel_module.indicators = indicators_module
    panel_module.pane = pane_module
    panel_module.WidgetBox = _DummyWidget
    panel_module.Row = _DummyWidget
    panel_module.Column = _DummyWidget

    sys.modules["panel"] = panel_module
    sys.modules["panel.widgets"] = widgets_module
    sys.modules["panel.indicators"] = indicators_module
    sys.modules["panel.pane"] = pane_module


_install_panel_stub()

if not hasattr(numpy_stub, "__version__"):
    numpy_stub.__version__ = "0.0"

if not hasattr(numpy_stub, "dtype"):
    class _DummyDType:
        def __init__(self, value):
            self.type = value

    def _dtype(value):
        return _DummyDType(value)

    numpy_stub.dtype = _dtype


def _install_pandas_stub():
    if "pandas" in sys.modules:
        return

    class _FakeILoc:
        def __init__(self, data):
            self._data = list(data)

        def __getitem__(self, index):
            return self._data[index]

    class _FakeSeries(list):
        def __init__(self, data):
            super().__init__(data)
            self._data = list(data)
            self.iloc = _FakeILoc(self._data)

        def __eq__(self, other):
            return [value == other for value in self._data]

    class _FakeLoc:
        def __init__(self, frame):
            self._frame = frame

        def __getitem__(self, mask):
            filtered = {}
            for key, values in self._frame._data.items():
                filtered[key] = [val for val, keep in zip(values, mask) if keep]
            return _FakeDataFrame(filtered)

    class _FakeDataFrame:
        def __init__(self, data=None, columns=None):
            self._data = {}
            if data is None:
                data = {}
            if isinstance(data, dict):
                for key, values in data.items():
                    self._data[key] = list(values)
            elif isinstance(data, list):
                keys = set()
                for row in data:
                    keys.update(row.keys())
                for key in keys:
                    self._data[key] = [row.get(key) for row in data]
            else:
                raise TypeError("Unsupported data type for FakeDataFrame")
            if columns is not None:
                for column in columns:
                    self._data.setdefault(column, [])
            self.loc = _FakeLoc(self)

        def __getitem__(self, key):
            return _FakeSeries(self._data[key])

        def __len__(self):
            if not self._data:
                return 0
            return len(next(iter(self._data.values())))

        @property
        def empty(self):
            return len(self) == 0

        def to_dict(self):
            return {key: list(values) for key, values in self._data.items()}

        def assign(self, **kwargs):
            data = self.to_dict()
            length = len(self)
            for key, value in kwargs.items():
                if isinstance(value, list):
                    data[key] = list(value)
                else:
                    data[key] = [value] * length
            return _FakeDataFrame(data)

    def _concat(frames, ignore_index=False):
        data = {}
        for frame in frames:
            for key, values in frame._data.items():
                data.setdefault(key, [])
                data[key].extend(values)
        if ignore_index:
            return _FakeDataFrame(data)
        return _FakeDataFrame(data)

    def _json_normalize(records):
        return _FakeDataFrame(records)

    def _assert_frame_equal(left, right):
        assert left.to_dict() == right.to_dict()

    pandas_module = types.ModuleType("pandas")
    pandas_module.DataFrame = _FakeDataFrame
    pandas_module.concat = _concat
    pandas_module.json_normalize = _json_normalize

    testing_module = types.ModuleType("pandas.testing")
    testing_module.assert_frame_equal = _assert_frame_equal
    pandas_module.testing = testing_module

    sys.modules["pandas"] = pandas_module
    sys.modules["pandas.testing"] = testing_module


_install_pandas_stub()

from loraflexsim.launcher.simulator import Simulator
from loraflexsim.launcher import dashboard

pd = dashboard.pd


class _DummyIndicator:
    """Objet minimal possédant un attribut ``value``."""

    def __init__(self):
        self.value = None


class _DummyTable:
    """Objet minimal possédant un attribut ``object``."""

    def __init__(self):
        self.object = None


class _DummyButton:
    """Widget factice avec les attributs utilisés par ``on_stop``."""

    def __init__(self):
        self.disabled = True
        self.name = ""
        self.button_type = ""


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_step_simulation_updates_indicators(monkeypatch):
    """Vérifie que ``step_simulation`` alimente bien les indicateurs Panel."""

    monkeypatch.setattr(dashboard, "pdr_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "collisions_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "energy_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "delay_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "throughput_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "retrans_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "pdr_table", _DummyTable())
    monkeypatch.setattr(dashboard, "pause_button", _DummyButton())
    monkeypatch.setattr(dashboard, "fast_forward_button", _DummyButton())

    monkeypatch.setattr(dashboard, "update_histogram", lambda metrics: None)
    monkeypatch.setattr(dashboard, "update_map", lambda: None)
    monkeypatch.setattr(dashboard, "update_timeline", lambda: None)
    monkeypatch.setattr(
        dashboard,
        "session_alive",
        lambda doc=None, state_container=None: True,
    )

    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        packets_to_send=1,
        mobility=False,
        seed=1,
    )

    dashboard.sim = sim
    dashboard.current_run = 1
    dashboard.runs_metrics_timeline = [None]

    while True:
        result = dashboard.step_simulation()
        if result is False:
            break
        if not getattr(sim, "running", False):
            break

    metrics = sim.get_metrics()

    assert dashboard.pdr_indicator.value == pytest.approx(metrics["PDR"])
    assert dashboard.collisions_indicator.value == metrics["collisions"]
    assert dashboard.energy_indicator.value == pytest.approx(metrics["energy_J"])
    assert dashboard.delay_indicator.value == pytest.approx(metrics["avg_delay_s"])
    assert dashboard.throughput_indicator.value == pytest.approx(
        metrics["throughput_bps"]
    )
    assert dashboard.retrans_indicator.value == metrics["retransmissions"]

    table_df = dashboard.pdr_table.object
    expected_pdr = metrics["pdr_by_node"]
    expected_recent = metrics["recent_pdr_by_node"]

    assert pd is not None
    assert isinstance(table_df, pd.DataFrame)
    assert set(table_df["Node"]) == set(expected_pdr.keys())
    for node_id, pdr_value in expected_pdr.items():
        row = table_df.loc[table_df["Node"] == node_id]
        assert not row.empty
        assert row["PDR"].iloc[0] == pytest.approx(pdr_value)
        assert row["Recent PDR"].iloc[0] == pytest.approx(expected_recent[node_id])

    timeline_expected = sim.get_metrics_timeline()
    timeline_recorded = dashboard.runs_metrics_timeline[0]

    if isinstance(timeline_expected, pd.DataFrame):
        pd.testing.assert_frame_equal(timeline_recorded, timeline_expected)
    else:
        assert timeline_recorded == timeline_expected
