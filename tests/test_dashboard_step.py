"""Tests pour la fonction ``step_simulation`` du tableau de bord Panel."""

import csv
from collections import deque
import sys
import types

import numpy_stub
import plotly.graph_objects as go
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

if not hasattr(numpy_stub, "integer"):
    numpy_stub.integer = int


def _install_pandas_stub():
    if "pandas" in sys.modules:
        return

    def _convert_value(value):
        if value is None or value == "":
            return None
        if isinstance(value, (int, float, bool)):
            return value
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        try:
            if any(ch in lower for ch in ["e", "."]):
                number = float(value)
                return number
            number = int(value)
            return number
        except (TypeError, ValueError):
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        return value

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

        def sum(self):
            return sum(value for value in self._data if value is not None)

        def mean(self):
            values = [value for value in self._data if value is not None]
            return sum(values) / len(values) if values else 0

        def max(self):
            values = [value for value in self._data if value is not None]
            return max(values) if values else None

        def min(self):
            values = [value for value in self._data if value is not None]
            return min(values) if values else None

        def isin(self, candidates):
            candidate_set = set(candidates)
            return _FakeSeries([value in candidate_set for value in self._data])

        def tolist(self):
            return list(self._data)

    class _FakeIndex(_FakeSeries):
        pass

    class _FakeLoc:
        def __init__(self, frame):
            self._frame = frame

        def __getitem__(self, mask):
            filtered = {}
            for key, values in self._frame._data.items():
                filtered[key] = [val for val, keep in zip(values, mask) if keep]
            return _FakeDataFrame(filtered)

    class _FakeRow(dict):
        pass

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
            if isinstance(key, str):
                if key not in self._data:
                    raise KeyError(key)
                return _FakeSeries(self._data[key])
            if isinstance(key, (list, tuple)):
                if key and all(isinstance(item, str) for item in key):
                    return _FakeDataFrame({col: self._data.get(col, []) for col in key})
                return self._filter_rows(list(key))
            if isinstance(key, _FakeSeries):
                return self._filter_rows(list(key))
            if isinstance(key, list):
                return self._filter_rows(key)
            raise KeyError(key)

        def __setitem__(self, key, value):
            length = len(self)
            if isinstance(value, list):
                self._data[key] = list(value)
            else:
                self._data[key] = [value] * length

        def __len__(self):
            if not self._data:
                return 0
            return len(next(iter(self._data.values())))

        @property
        def empty(self):
            return len(self) == 0

        def to_dict(self, orient=None):
            if orient in (None, "dict"):
                return {key: list(values) for key, values in self._data.items()}
            if orient in ("records",):
                records = []
                for idx in range(len(self)):
                    records.append({key: values[idx] for key, values in self._data.items()})
                return records
            raise ValueError(f"Unsupported orient: {orient}")

        def to_csv(self, path, index=True, **_kwargs):
            records = self.to_dict("records")
            if not records:
                with open(path, "w", encoding="utf-8", newline="") as handle:
                    if index:
                        handle.write("index\n")
                return
            columns = list(self._data.keys())
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                if index:
                    writer.writerow(["index", *columns])
                    for idx, row in enumerate(records):
                        writer.writerow([idx] + [row.get(col) for col in columns])
                else:
                    writer.writerow(columns)
                    for row in records:
                        writer.writerow([row.get(col) for col in columns])

        def copy(self):
            return _FakeDataFrame(self.to_dict())

        @property
        def columns(self):
            return list(self._data.keys())

        def assign(self, **kwargs):
            data = self.to_dict()
            length = len(self)
            for key, value in kwargs.items():
                if isinstance(value, list):
                    data[key] = list(value)
                else:
                    data[key] = [value] * length
            return _FakeDataFrame(data)

        def insert(self, _loc, column, value):
            if column in self._data:
                return
            if isinstance(value, list):
                self._data[column] = list(value)
            else:
                self._data[column] = [value] * len(self)

        def drop_duplicates(self, subset=None):
            seen = set()
            unique_rows = []
            records = self.to_dict("records")
            for record in records:
                if subset is None:
                    key = tuple(sorted(record.items()))
                else:
                    key = tuple(record.get(col) for col in subset)
                if key in seen:
                    continue
                seen.add(key)
                unique_rows.append(record)
            return _FakeDataFrame(unique_rows)

        def apply(self, func, axis=0):
            if axis == 1:
                results = []
                for record in self.to_dict("records"):
                    results.append(func(_FakeRow(record)))
                return _FakeSeries(results)
            raise NotImplementedError("Only axis=1 is supported in the stub")

        def sum(self):
            totals = {}
            for key, values in self._data.items():
                totals[key] = sum(v for v in values if v is not None)
            return totals

        def mean(self):
            averages = {}
            for key, values in self._data.items():
                valid = [v for v in values if v is not None]
                averages[key] = sum(valid) / len(valid) if valid else 0
            return averages

        def _filter_rows(self, mask):
            if len(mask) != len(self):
                raise ValueError("Boolean index has wrong length")
            filtered = {}
            for key, values in self._data.items():
                filtered[key] = [val for val, keep in zip(values, mask) if bool(keep)]
            return _FakeDataFrame(filtered)

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

    def _read_csv(path, **_kwargs):
        with open(path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = []
            for raw in reader:
                parsed = {key: _convert_value(value) for key, value in raw.items()}
                rows.append(parsed)
        return _FakeDataFrame(rows)

    pandas_module = types.ModuleType("pandas")
    pandas_module.DataFrame = _FakeDataFrame
    pandas_module.Series = _FakeSeries
    pandas_module.Index = _FakeIndex
    pandas_module.concat = _concat
    pandas_module.json_normalize = _json_normalize
    pandas_module.read_csv = _read_csv

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
    monkeypatch.setattr(dashboard, "_update_metrics_timeline_pane", lambda *_: None)
    original_set_metrics = dashboard._set_metric_indicators
    instant_history: list[tuple[dict, float, float, float, float, float, float]] = []

    def _record_and_set(metrics: dict | None) -> None:
        original_set_metrics(metrics)
        if metrics and "instant_throughput_bps" in metrics:
            instant_history.append(
                (
                    dict(metrics),
                    dashboard.pdr_indicator.value,
                    dashboard.collisions_indicator.value,
                    dashboard.energy_indicator.value,
                    dashboard.delay_indicator.value,
                    dashboard.throughput_indicator.value,
                    dashboard.retrans_indicator.value,
                )
            )

    monkeypatch.setattr(dashboard, "_set_metric_indicators", _record_and_set)
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
    assert instant_history
    (
        metrics_from_step,
        pdr_value,
        collisions_value,
        energy_value,
        delay_value,
        throughput_value,
        retrans_value,
    ) = instant_history[-1]

    assert pdr_value == pytest.approx(metrics_from_step["PDR"])
    assert collisions_value == metrics_from_step["collisions"]
    assert energy_value == pytest.approx(metrics_from_step["energy_J"])
    assert delay_value == pytest.approx(metrics_from_step["instant_avg_delay_s"])
    assert throughput_value == pytest.approx(
        metrics_from_step["instant_throughput_bps"]
    )
    assert retrans_value == metrics_from_step["retransmissions"]

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

    def _timeline_to_frame(timeline):
        if isinstance(timeline, pd.DataFrame):
            records = timeline.to_dict("records")
            return pd.DataFrame(records)
        if timeline is None:
            return pd.DataFrame()
        return pd.DataFrame(list(timeline))

    expected_df = _timeline_to_frame(timeline_expected)
    recorded_df = _timeline_to_frame(timeline_recorded)
    pd.testing.assert_frame_equal(recorded_df, expected_df)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_step_simulation_updates_after_server_delay(monkeypatch):
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
    monkeypatch.setattr(dashboard, "_update_metrics_timeline_pane", lambda *_: None)
    monkeypatch.setattr(dashboard, "session_alive", lambda doc=None, state_container=None: True)

    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        packets_to_send=1,
        mobility=False,
        flora_mode=True,
        flora_timing=True,
        duty_cycle=None,
        area_size=10.0,
        seed=42,
    )
    if sim.nodes and sim.gateways:
        node = sim.nodes[0]
        gateway = sim.gateways[0]
        node.x = node.y = 0.0
        node.initial_x = node.initial_y = 0.0
        gateway.x = gateway.y = 0.0

    dashboard.sim = sim
    dashboard.current_run = 1
    dashboard.runs_metrics_timeline = [None]

    metrics_history: list[dict] = []
    original_set_metrics = dashboard._set_metric_indicators

    def _capture_metrics(metrics: dict | None) -> None:
        original_set_metrics(metrics)
        if metrics:
            metrics_history.append(dict(metrics))

    monkeypatch.setattr(dashboard, "_set_metric_indicators", _capture_metrics)

    while True:
        result = dashboard.step_simulation()
        if result is False:
            break
        if not getattr(sim, "running", False):
            break

    assert metrics_history, "Aucun instantané métrique enregistré"
    delivered_indices = [idx for idx, entry in enumerate(metrics_history) if entry["delivered"] > 0]
    assert delivered_indices, "La livraison n'a jamais été enregistrée"
    first_success = delivered_indices[0]

    for idx in range(first_success):
        entry = metrics_history[idx]
        assert entry["delivered"] == 0
        assert entry["PDR"] == pytest.approx(0.0)
        assert entry["instant_avg_delay_s"] == pytest.approx(0.0)
        assert entry["instant_throughput_bps"] == pytest.approx(0.0)

    success_entry = metrics_history[first_success]
    assert success_entry["PDR"] == pytest.approx(1.0)
    assert success_entry["instant_avg_delay_s"] > 0.0
    assert success_entry["instant_throughput_bps"] > 0.0


class _TimelinePane:
    def __init__(self):
        self.object = None


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_step_simulation_limits_timeline_refresh(monkeypatch):
    monkeypatch.setattr(dashboard, "pdr_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "collisions_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "energy_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "delay_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "throughput_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "retrans_indicator", _DummyIndicator())
    monkeypatch.setattr(dashboard, "pdr_table", _DummyTable())
    monkeypatch.setattr(dashboard, "pause_button", _DummyButton())
    monkeypatch.setattr(dashboard, "fast_forward_button", _DummyButton())

    pane = _TimelinePane()
    monkeypatch.setattr(dashboard, "metrics_timeline_pane", pane)

    monkeypatch.setattr(dashboard, "update_histogram", lambda metrics: None)
    monkeypatch.setattr(dashboard, "update_map", lambda: None)
    monkeypatch.setattr(dashboard, "update_timeline", lambda: None)
    monkeypatch.setattr(
        dashboard,
        "session_alive",
        lambda doc=None, state_container=None: True,
    )

    refresh_calls = 0

    class _DummyScatter:
        def __init__(self, x, y, mode=None, name=None):
            self.x = list(x)
            self.y = list(y)
            self.name = name

        def update(self, *, x, y):
            self.x = list(x)
            self.y = list(y)

    class _DummyFigure:
        def __init__(self):
            self.data: list[_DummyScatter] = []

        def add_trace(self, trace):
            self.data.append(trace)

        def add_scatter(self, x, y, mode=None, name=None, **_):
            self.add_trace(_DummyScatter(x, y, mode=mode, name=name))

        def update_layout(self, **_):
            pass

    def _simple_build(timeline):
        nonlocal refresh_calls
        refresh_calls += 1
        fig = _DummyFigure()
        if not timeline:
            return fig
        if hasattr(timeline, "to_dict"):
            records = timeline.to_dict("records")
        else:
            records = list(timeline)
        times = [entry.get("time_s") for entry in records if "time_s" in entry]
        pdr_values = [entry.get("PDR") for entry in records if "PDR" in entry]
        if times and pdr_values:
            fig.add_scatter(x=times, y=pdr_values, mode="lines+markers", name="PDR")
        return fig

    dummy_go = types.SimpleNamespace(Figure=_DummyFigure, Scatter=_DummyScatter)
    monkeypatch.setattr(dashboard, "go", dummy_go)
    monkeypatch.setattr(sys.modules[__name__], "go", dummy_go, raising=False)
    monkeypatch.setattr(dashboard, "_build_metrics_timeline_figure", _simple_build)
    monkeypatch.setattr(dashboard, "METRICS_TIMELINE_FULL_REFRESH_INTERVAL", 5)
    dashboard._metrics_timeline_steps_since_refresh = 0
    dashboard.metrics_timeline_buffer = []
    dashboard.metrics_timeline_window = deque(
        maxlen=dashboard.METRICS_TIMELINE_WINDOW_SIZE
    )
    dashboard.export_message = _DummyTable()

    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        packets_to_send=25,
        mobility=False,
        seed=123,
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

    timeline_count = len(sim.metrics_timeline)
    assert timeline_count > 0

    expected_refreshes = 1 + max(0, (timeline_count - 1) // 5)
    expected_total_calls = expected_refreshes + 1  # rafraîchissement final via on_stop
    assert refresh_calls <= timeline_count
    assert isinstance(pane.object, _DummyFigure)

    trace = next((tr for tr in pane.object.data if tr.name == "PDR"), None)
    assert trace is not None
    assert len(trace.x) == timeline_count


def test_set_metric_indicators_prefers_instant_values(monkeypatch):
    """Les indicateurs doivent refléter les métriques instantanées si présentes."""

    pdr = _DummyIndicator()
    collisions = _DummyIndicator()
    energy = _DummyIndicator()
    delay = _DummyIndicator()
    throughput = _DummyIndicator()
    retrans = _DummyIndicator()

    monkeypatch.setattr(dashboard, "pdr_indicator", pdr)
    monkeypatch.setattr(dashboard, "collisions_indicator", collisions)
    monkeypatch.setattr(dashboard, "energy_indicator", energy)
    monkeypatch.setattr(dashboard, "delay_indicator", delay)
    monkeypatch.setattr(dashboard, "throughput_indicator", throughput)
    monkeypatch.setattr(dashboard, "retrans_indicator", retrans)

    first_metrics = {
        "PDR": 0.25,
        "collisions": 1.0,
        "energy_J": 0.5,
        "instant_avg_delay_s": 2.5,
        "avg_delay_s": 3.0,
        "instant_throughput_bps": 128.0,
        "throughput_bps": 64.0,
        "retransmissions": 0.0,
    }
    dashboard._set_metric_indicators(first_metrics)

    assert pdr.value == pytest.approx(0.25)
    assert collisions.value == pytest.approx(1.0)
    assert energy.value == pytest.approx(0.5)
    assert delay.value == pytest.approx(2.5)
    assert throughput.value == pytest.approx(128.0)
    assert retrans.value == pytest.approx(0.0)

    second_metrics = {
        "PDR": 0.5,
        "collisions": 2.0,
        "energy_J": 1.5,
        "instant_avg_delay_s": 1.5,
        "avg_delay_s": 1.8,
        "instant_throughput_bps": 256.0,
        "throughput_bps": 180.0,
        "retransmissions": 1.0,
    }
    dashboard._set_metric_indicators(second_metrics)

    assert pdr.value == pytest.approx(0.5)
    assert collisions.value == pytest.approx(2.0)
    assert energy.value == pytest.approx(1.5)
    assert delay.value == pytest.approx(1.5)
    assert throughput.value == pytest.approx(256.0)
    assert retrans.value == pytest.approx(1.0)

    fallback_metrics = {
        "PDR": 0.75,
        "collisions": 3.0,
        "energy_J": 2.5,
        "avg_delay_s": 4.0,
        "throughput_bps": 512.0,
        "retransmissions": 2.0,
    }
    dashboard._set_metric_indicators(fallback_metrics)

    assert pdr.value == pytest.approx(0.75)
    assert collisions.value == pytest.approx(3.0)
    assert energy.value == pytest.approx(2.5)
    assert delay.value == pytest.approx(4.0)
    assert throughput.value == pytest.approx(512.0)
    assert retrans.value == pytest.approx(2.0)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_setup_simulation_resets_timeline_between_runs(monkeypatch):
    """Deux lancements successifs doivent repartir d'une timeline vide."""

    monkeypatch.setattr(dashboard, "update_map", lambda: None)
    monkeypatch.setattr(dashboard, "update_histogram", lambda _metrics: None)
    monkeypatch.setattr(dashboard, "_update_metrics_timeline_pane", lambda *_: None)

    def _fake_update_timeline():
        fig = dashboard.timeline_fig
        if not isinstance(fig, dashboard.go.Figure):
            fig = dashboard.go.Figure()
            dashboard.timeline_fig = fig
        fig.add_scatter(x=[0.0, 1.0], y=[0, 0], mode="lines", line=dict(color="blue"))
        dashboard.last_event_index += 1
        dashboard.timeline_pane.object = fig

    monkeypatch.setattr(dashboard, "update_timeline", _fake_update_timeline)
    monkeypatch.setattr(
        dashboard,
        "session_alive",
        lambda doc=None, state_container=None: True,
    )

    dashboard._cleanup_callbacks()
    dashboard.sim = None
    dashboard.sim_callback = None
    dashboard.map_anim_callback = None
    dashboard.chrono_callback = None
    dashboard.current_run = 1
    dashboard.total_runs = 1
    dashboard.runs_events.clear()
    dashboard.runs_metrics.clear()
    dashboard.runs_metrics_timeline.clear()
    dashboard.packets_input.value = 1
    dashboard.num_runs_input.value = 1
    dashboard.real_time_duration_input.value = 0

    dashboard.setup_simulation()

    assert dashboard.sim is not None
    assert getattr(dashboard.sim, "running", False)

    while getattr(dashboard.sim, "running", False):
        dashboard.step_simulation()

    old_figure = dashboard.timeline_fig
    assert len(old_figure.data) > 0
    assert dashboard.timeline_pane.object is old_figure
    assert dashboard.last_event_index > 0

    dashboard.sim = None
    dashboard.current_run = 1
    dashboard.runs_events.clear()
    dashboard.runs_metrics.clear()
    dashboard.runs_metrics_timeline.clear()

    dashboard.setup_simulation()

    try:
        assert dashboard.timeline_fig is not old_figure
        assert dashboard.last_event_index == 0
        assert len(dashboard.timeline_fig.data) == 0
        assert dashboard.timeline_pane.object is dashboard.timeline_fig
        assert len(dashboard.timeline_pane.object.data) == 0
    finally:
        dashboard.on_stop(None)
        dashboard._cleanup_callbacks()
        dashboard.sim = None
