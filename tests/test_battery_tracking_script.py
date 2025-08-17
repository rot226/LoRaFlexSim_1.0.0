import sys
import pathlib


def test_battery_tracking_script(tmp_path, monkeypatch):
    repo_root = pathlib.Path(__file__).resolve().parents[1]

    # Import real numpy/pandas by temporarily removing the repository path
    original_path = sys.path.copy()
    if '' in sys.path:
        sys.path.remove('')
    if str(repo_root) in sys.path:
        sys.path.remove(str(repo_root))
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    sys.path = original_path

    from scripts import run_battery_tracking, plot_battery_tracking

    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setattr(run_battery_tracking, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", [
        "run_battery_tracking.py",
        "--nodes",
        "1",
        "--packets",
        "1",
        "--seed",
        "1",
    ])
    run_battery_tracking.main()
    csv_path = tmp_path / "battery_tracking.csv"
    assert csv_path.is_file()

    figures_dir = tmp_path / "figures"
    monkeypatch.setattr(plot_battery_tracking, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(plot_battery_tracking, "FIGURES_DIR", figures_dir)
    plot_battery_tracking.main()
    png_path = figures_dir / "battery_tracking.png"
    assert png_path.is_file()

    png_path.unlink()
    figures_dir.rmdir()
    csv_path.unlink()
