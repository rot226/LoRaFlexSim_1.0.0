import importlib
import sys
import types
from pathlib import Path


def test_save_multi_format_cli(tmp_path, monkeypatch):
    # Minimal matplotlib stub
    class _Figure:
        def savefig(self, filename, dpi=None):
            Path(filename).touch()

    def _figure():
        return _Figure()

    plt_module = types.ModuleType("pyplot")
    plt_module.figure = _figure

    matplotlib_module = types.ModuleType("matplotlib")
    matplotlib_module.pyplot = plt_module

    monkeypatch.setitem(sys.modules, "matplotlib", matplotlib_module)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", plt_module)

    plotting = importlib.import_module("loraflexsim.utils.plotting")
    plotting.main([str(tmp_path / "out"), "--formats", "png,jpg,eps"])

    for ext in ("png", "jpg", "eps"):
        assert (tmp_path / f"out.{ext}").is_file()
