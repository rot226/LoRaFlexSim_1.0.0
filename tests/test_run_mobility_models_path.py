import sys

from scripts import run_mobility_models


def test_run_mobility_models_path(tmp_path, monkeypatch):
    # Create simple 2x2 path map with all cells traversable
    map_file = tmp_path / "map.txt"
    map_file.write_text("0 0\n0 0\n")

    results_dir = tmp_path / "results"
    monkeypatch.setattr(run_mobility_models, "RESULTS_DIR", results_dir)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_mobility_models.py",
            "--model",
            "path",
            "--path-map",
            str(map_file),
            "--nodes",
            "1",
            "--packets",
            "1",
            "--seed",
            "1",
        ],
    )

    run_mobility_models.main()

    csv_file = results_dir / "mobility_models.csv"
    assert csv_file.is_file()
    lines = csv_file.read_text().splitlines()
    assert lines[0].split(",")[0] + "," + lines[1].split(",")[0] == "model,path"
