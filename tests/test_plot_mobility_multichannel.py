import pytest
from pathlib import Path

try:  # pragma: no cover - exercised at import time
    import pandas  # noqa: F401
except Exception:  # pragma: no cover
    pytest.skip('pandas import failed', allow_module_level=True)

import matplotlib
matplotlib.use('Agg')
from scripts import plot_mobility_multichannel


def test_plot_mobility_multichannel(tmp_path, monkeypatch):
    figures = []
    original_subplots = plot_mobility_multichannel.plt.subplots

    def spy_subplots(*args, **kwargs):
        fig, ax = original_subplots(*args, **kwargs)
        figures.append(ax)
        return fig, ax

    monkeypatch.setattr(plot_mobility_multichannel.plt, 'subplots', spy_subplots)

    csv_path = Path('tests/data/mobility_multichannel_summary.csv')
    plot_mobility_multichannel.plot(str(csv_path), str(tmp_path))

    for ext in ("png", "jpg", "eps"):
        assert (tmp_path / f"pdr_vs_scenario.{ext}").is_file()

    tick_labels = [tick.get_text() for tick in figures[0].get_xticklabels()]
    assert all("N=" in label and "C=" in label for label in tick_labels)
