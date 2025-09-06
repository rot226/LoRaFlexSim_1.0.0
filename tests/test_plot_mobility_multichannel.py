from pathlib import Path
import importlib
import sys
import types


def test_plot(tmp_path, monkeypatch):
    # Use the real numpy module so that pandas can be imported.
    stubs_dir = Path(__file__).resolve().parent / 'stubs'
    path_no_stubs = [p for p in sys.path if p != str(stubs_dir)]
    monkeypatch.setattr(sys, 'path', path_no_stubs)
    monkeypatch.delitem(sys.modules, 'numpy', raising=False)
    monkeypatch.delitem(sys.modules, 'numpy.random', raising=False)
    np = importlib.import_module('numpy')
    sys.modules['numpy'] = np
    sys.modules['numpy.random'] = np.random

    # Minimal matplotlib stand-ins.
    class _Figure:
        def savefig(self, filename, dpi=None):
            pass

        def tight_layout(self, *args, **kwargs):
            pass

    class _Tick:
        def __init__(self, text):
            self._text = text

        def get_text(self):
            return self._text

    class _Axes:
        def __init__(self):
            self._labels = []

        def bar(self, *args, **kwargs):
            return []

        def set_xlabel(self, *args, **kwargs):
            pass

        def set_xticks(self, ticks):
            pass

        def set_xticklabels(self, labels, **kwargs):
            self._labels = list(labels)

        def set_ylabel(self, *args, **kwargs):
            pass

        def axhline(self, *args, **kwargs):
            pass

        def set_ylim(self, *args, **kwargs):
            pass

        def set_title(self, *args, **kwargs):
            pass

        def bar_label(self, *args, **kwargs):
            pass

        def legend(self, *args, **kwargs):
            pass

        def get_xticklabels(self):
            return [_Tick(label) for label in self._labels]

    def _subplots(*args, **kwargs):
        return _Figure(), _Axes()

    def _close(fig=None):
        pass

    plt_module = types.ModuleType('pyplot')
    plt_module.subplots = _subplots
    plt_module.close = _close

    figure_module = types.ModuleType('figure')
    figure_module.Figure = _Figure

    matplotlib_module = types.ModuleType('matplotlib')
    matplotlib_module.pyplot = plt_module
    matplotlib_module.figure = figure_module

    monkeypatch.setitem(sys.modules, 'matplotlib', matplotlib_module)
    monkeypatch.setitem(sys.modules, 'matplotlib.pyplot', plt_module)
    monkeypatch.setitem(sys.modules, 'matplotlib.figure', figure_module)

    plot_module = importlib.import_module('scripts.plot_mobility_multichannel')

    def fake_savefig(self, filename, dpi=None):
        Path(filename).touch()

    monkeypatch.setattr(figure_module.Figure, 'savefig', fake_savefig)
    monkeypatch.setattr(plt_module, 'close', lambda fig=None: None)

    captured = {}
    orig_subplots = plt_module.subplots

    def fake_subplots(*args, **kwargs):
        fig, ax = orig_subplots(*args, **kwargs)
        captured['ax'] = ax
        return fig, ax

    monkeypatch.setattr(plt_module, 'subplots', fake_subplots)

    csv_path = Path('tests/data/mobility_multichannel_summary.csv')
    plot_module.plot(str(csv_path), tmp_path)

    for ext in ('png', 'jpg', 'eps'):
        assert (tmp_path / f'pdr_vs_scenario.{ext}').is_file()

    labels = [tick.get_text() for tick in captured['ax'].get_xticklabels()]
    assert labels
    for label in labels:
        assert 'N=' in label and 'C=' in label
