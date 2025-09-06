import csv
import pytest
from pathlib import Path

try:  # pragma: no cover - exercised at import time
    import pandas  # noqa: F401
except Exception:  # pragma: no cover
    pytest.skip('pandas import failed', allow_module_level=True)

from scripts import run_mobility_multichannel


def test_run_mobility_multichannel(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mobility_multichannel, 'RESULTS_DIR', tmp_path)
    run_mobility_multichannel.main([
        '--nodes', '1',
        '--packets', '1',
        '--replicates', '1',
        '--seed', '1',
    ])
    out_csv = tmp_path / 'mobility_multichannel.csv'
    assert out_csv.is_file()
    with out_csv.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows, 'CSV should contain data'
    row = rows[0]
    assert 'nodes' in row and 'channels' in row
    for metric in ['pdr', 'collision_rate', 'avg_delay_s', 'energy_per_node', 'avg_sf']:
        assert f'{metric}_mean' in row
        assert f'{metric}_std' in row
