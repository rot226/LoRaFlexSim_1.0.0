import sys
import pathlib


def test_plot_mobility_multichannel(tmp_path, monkeypatch):
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    stubs_dir = repo_root / "tests" / "stubs"
    original_path = sys.path.copy()
    if str(stubs_dir) in sys.path:
        sys.path.remove(str(stubs_dir))
    stub_numpy = sys.modules.pop("numpy", None)
    stub_numpy_random = sys.modules.pop("numpy.random", None)
    stub_pandas = sys.modules.pop("pandas", None)

    import numpy  # noqa: F401
    import pandas  # noqa: F401
    from scripts import plot_mobility_multichannel

    monkeypatch.setenv("MPLBACKEND", "Agg")
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure

    captured = {}
    real_subplots = plt.subplots

    def fake_subplots(*args, **kwargs):
        fig, ax = real_subplots(*args, **kwargs)
        captured["ax"] = ax
        return fig, ax

    monkeypatch.setattr(plt, "subplots", fake_subplots)
    monkeypatch.setattr(plt, "close", lambda fig: None)

    def fake_savefig(self, path, *args, **kwargs):
        pathlib.Path(path).touch()

    monkeypatch.setattr(Figure, "savefig", fake_savefig)

    csv_path = repo_root / "tests" / "data" / "mobility_multichannel_summary.csv"
    plot_mobility_multichannel.plot(str(csv_path), tmp_path)

    for ext in ("png", "jpg", "eps"):
        assert (tmp_path / f"pdr_vs_scenario.{ext}").is_file()

    ax = captured["ax"]
    for tick in ax.get_xticklabels():
        text = tick.get_text()
        assert "N=" in text and "C=" in text

    sys.path = original_path
    sys.modules.pop("numpy", None)
    sys.modules.pop("numpy.random", None)
    sys.modules.pop("pandas", None)
    if stub_numpy is not None:
        sys.modules["numpy"] = stub_numpy
    if stub_numpy_random is not None:
        sys.modules["numpy.random"] = stub_numpy_random
    if stub_pandas is not None:
        sys.modules["pandas"] = stub_pandas
