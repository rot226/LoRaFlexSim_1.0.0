"""Tests for the lightweight FLoRa reference loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from loraflexsim.validation.reference_loader import load_reference_metrics


def test_load_reference_metrics_from_sca():
    """The loader matches the known values from a FLoRa .sca capture."""

    path = Path("tests/integration/data/long_range_flora.sca")
    metrics = load_reference_metrics(path)
    assert metrics["sent"] == pytest.approx(72)
    assert metrics["received"] == pytest.approx(65)
    assert metrics["collisions"] == pytest.approx(0)
    assert metrics["PDR"] == pytest.approx(65 / 72)
    assert metrics["snr"] == pytest.approx(-1.9413691511020699)


def test_load_reference_metrics_from_csv(tmp_path):
    """CSV exports are aggregated without relying on pandas."""

    csv_file = tmp_path / "metrics.csv"
    csv_file.write_text(
        "sent,received,collisions,snr\n"
        "10,9,1,1.5\n"
        "5,4,0,2.5\n",
        encoding="utf-8",
    )

    metrics = load_reference_metrics(csv_file)
    assert metrics["sent"] == pytest.approx(15)
    assert metrics["received"] == pytest.approx(13)
    assert metrics["collisions"] == pytest.approx(1)
    assert metrics["PDR"] == pytest.approx(13 / 15)
    assert metrics["snr"] == pytest.approx((1.5 + 2.5) / 2)
