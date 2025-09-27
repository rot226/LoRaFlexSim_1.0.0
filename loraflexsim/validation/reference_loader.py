"""Utilities to load FLoRa reference metrics without pandas."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

Number = float | int


def load_reference_metrics(path: Path | str) -> dict[str, float]:
    """Aggregate reference metrics from a FLoRa export.

    The loader supports single ``.sca`` files, CSV exports and directories
    containing one or multiple ``.sca`` captures. Only the metrics required by
    the validation matrix (PDR, collisions and average SNR) are computed.
    """

    rows = list(_iter_reference_rows(Path(path)))
    if not rows:
        return {"sent": 0.0, "received": 0.0, "PDR": 0.0, "collisions": 0.0, "snr": 0.0}

    total_sent = sum(_as_int(row.get("sent")) for row in rows)
    total_received = sum(_as_int(row.get("received")) for row in rows)
    total_collisions = sum(_as_int(row.get("collisions")) for row in rows)

    snr_values = [_as_float(row.get("snr")) for row in rows if row.get("snr") is not None]
    snr_values = [val for val in snr_values if val is not None]
    avg_snr = sum(snr_values) / len(snr_values) if snr_values else 0.0

    pdr = (total_received / total_sent) if total_sent else 0.0

    return {
        "sent": float(total_sent),
        "received": float(total_received),
        "PDR": float(pdr),
        "collisions": float(total_collisions),
        "snr": float(avg_snr),
    }


def _iter_reference_rows(path: Path) -> Iterable[dict[str, Number]]:
    if path.is_dir():
        for sca_file in sorted(path.glob("*.sca")):
            yield _parse_sca_file(sca_file)
        return

    suffix = path.suffix.lower()
    if suffix == ".sca":
        yield _parse_sca_file(path)
    else:
        yield from _read_csv_file(path)


def _parse_sca_file(path: Path) -> dict[str, Number]:
    metrics: dict[str, float] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) < 4 or parts[0] != "scalar":
                continue
            name = parts[2].strip('"')
            try:
                value = float(parts[3])
            except ValueError:
                continue
            metrics[name] = metrics.get(name, 0.0) + value

    row: dict[str, Number] = {}
    for key, value in metrics.items():
        if key in {"sent", "received", "collisions"}:
            row[key] = int(round(value))
        elif key in {"snr", "rssi"}:
            row[key] = float(value)
    return row


def _read_csv_file(path: Path) -> Iterable[dict[str, Number]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row: dict[str, Number] = {}
            for key in ("sent", "received", "collisions", "snr"):
                if key not in raw:
                    continue
                value = raw[key]
                if value in (None, ""):
                    continue
                number = _as_float(value)
                if number is None:
                    continue
                if key in {"sent", "received", "collisions"}:
                    row[key] = int(round(number))
                else:
                    row[key] = float(number)
            if row:
                yield row


def _as_float(value: Number | str | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Number | str | None) -> int:
    float_value = _as_float(value) or 0.0
    return int(round(float_value))
