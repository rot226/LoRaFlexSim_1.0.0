"""Utilities to compare simulator results against FLoRa output."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

try:  # pandas est optionnel pour analyser les métriques de référence
    import pandas as pd
except Exception:  # pragma: no cover - pandas peut ne pas être installé
    pd = None

from loraflexsim.validation.reference_loader import load_reference_metrics


def _metrics_from_reference(reference: dict[str, Any]) -> dict[str, Any]:
    collisions = int(round(reference.get("collisions", 0.0)))
    return {
        "PDR": float(reference.get("PDR", 0.0)),
        "sf_distribution": {},
        "throughput_bps": float(reference.get("throughput_bps", 0.0)),
        "energy_J": float(reference.get("energy_J", 0.0)),
        "avg_delay_s": float(reference.get("avg_delay_s", 0.0)),
        "collision_distribution": {},
        "collisions": collisions,
    }


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            parsed: dict[str, Any] = {}
            for key, value in raw.items():
                if value in (None, ""):
                    continue
                lowered = value.lower()
                if lowered == "true":
                    parsed[key] = True
                    continue
                if lowered == "false":
                    parsed[key] = False
                    continue
                try:
                    number = float(value)
                except ValueError:
                    parsed[key] = value
                    continue
                if number.is_integer():
                    parsed[key] = int(number)
                else:
                    parsed[key] = number
            rows.append(parsed)
    return rows


def _aggregate_rows_no_pandas(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "sf_distribution": {},
            "throughput_bps": 0.0,
            "energy_J": 0.0,
            "avg_delay_s": 0.0,
            "collision_distribution": {},
            "collisions": 0,
        }

    sf_hist: dict[int, int] = {}
    collision_hist: dict[int, int] = {}
    energy_values: list[float] = []
    throughput_values: list[float] = []
    avg_delay_values: list[float] = []
    energy_class_values: dict[str, list[float]] = {}
    total_collisions = 0

    for row in rows:
        if "collisions" in row and row["collisions"] is not None:
            total_collisions += int(row["collisions"])
        if "throughput_bps" in row and row["throughput_bps"] is not None:
            throughput_values.append(float(row["throughput_bps"]))
        if "avg_delay_s" in row and row["avg_delay_s"] is not None:
            avg_delay_values.append(float(row["avg_delay_s"]))
        if "energy_J" in row and row["energy_J"] is not None:
            energy_values.append(float(row["energy_J"]))
        elif "energy" in row and row["energy"] is not None:
            energy_values.append(float(row["energy"]))

        for key, value in row.items():
            if value is None:
                continue
            if key.startswith("sf") and key[2:].isdigit():
                sf = int(key[2:])
                sf_hist[sf] = sf_hist.get(sf, 0) + int(value)
            elif key.startswith("collisions_sf"):
                suffix = key.split("sf", 1)[1]
                if suffix.isdigit():
                    sf = int(suffix)
                    collision_hist[sf] = collision_hist.get(sf, 0) + int(value)
            elif key.startswith("energy_class_"):
                parts = key.split("_")
                if len(parts) >= 3:
                    cls = parts[2]
                    energy_class_values.setdefault(cls, []).append(float(value))

    throughput = sum(throughput_values) / len(throughput_values) if throughput_values else 0.0
    avg_delay = sum(avg_delay_values) / len(avg_delay_values) if avg_delay_values else 0.0
    energy = sum(energy_values) / len(energy_values) if energy_values else 0.0
    energy_class = {
        f"energy_class_{cls}_J": sum(values) / len(values)
        for cls, values in energy_class_values.items()
        if values
    }

    return {
        "sf_distribution": sf_hist,
        "throughput_bps": throughput,
        "energy_J": energy,
        "avg_delay_s": avg_delay,
        "collision_distribution": collision_hist,
        "collisions": total_collisions,
        **energy_class,
    }

from .adr_standard_1 import apply as apply_adr_standard
from .lorawan import DR_TO_SF, LinkADRReq, TX_POWER_INDEX_TO_DBM
from .server import ADR_WINDOW_SIZE

if TYPE_CHECKING:
    from .simulator import Simulator


def _parse_sca_file(path: Path) -> dict[str, Any]:
    """Return raw metrics from an OMNeT++ ``.sca`` file.

    The resulting dictionary can be converted to a DataFrame to compute
    aggregates similar to a FLoRa CSV export.
    """
    metrics: dict[str, float] = {}
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] == "scalar":
                name = parts[2].strip('"')
                try:
                    value = float(parts[3])
                except ValueError:
                    continue
                if name in {"energy", "energy_J"}:
                    metrics["energy_J"] = metrics.get("energy_J", 0.0) + value
                else:
                    metrics[name] = metrics.get(name, 0.0) + value

    row: dict[str, Any] = {}
    for key, val in metrics.items():
        if key in {"sent", "received", "collisions"}:
            row[key] = int(val)
        elif key == "energy":
            row["energy_J"] = float(val)
        elif key in {"throughput_bps", "energy_J", "rssi", "snr", "avg_delay_s"}:
            row[key] = float(val)
        elif key.startswith("sf") and key[2:].isdigit():
            row[key] = int(val)
        elif key.startswith("collisions_sf"):
            row[key] = int(val)
        elif key.startswith("energy_class_"):
            row[key] = float(val)

    return row


def _aggregate_df(df: 'pd.DataFrame') -> dict[str, Any]:
    """Compute aggregated metrics from a DataFrame of raw values."""
    if pd is None:
        raise RuntimeError("pandas is required for this function")
    total_sent = int(df["sent"].sum()) if "sent" in df.columns else 0
    total_recv = int(df["received"].sum()) if "received" in df.columns else 0
    pdr = total_recv / total_sent if total_sent else 0.0

    sf_cols = [
        c
        for c in df.columns
        if c.startswith("sf") and not c.startswith("collisions_sf")
    ]
    sf_hist = {int(c[2:]): int(df[c].sum()) for c in sf_cols}

    throughput = (
        float(df["throughput_bps"].mean()) if "throughput_bps" in df.columns else 0.0
    )
    avg_delay = float(df["avg_delay_s"].mean()) if "avg_delay_s" in df.columns else 0.0
    if "energy_J" in df.columns:
        energy = float(df["energy_J"].mean())
    elif "energy" in df.columns:
        energy = float(df["energy"].mean())
    else:
        energy = 0.0

    collisions = int(df["collisions"].sum()) if "collisions" in df.columns else 0
    collision_cols = [c for c in df.columns if c.startswith("collisions_sf")]
    collision_dist = {int(c.split("sf")[1]): int(df[c].sum()) for c in collision_cols}

    energy_class = {
        col.split("_")[2]: float(df[col].mean())
        for col in df.columns
        if col.startswith("energy_class_")
    }

    return {
        "PDR": pdr,
        "sf_distribution": sf_hist,
        "throughput_bps": throughput,
        "energy_J": energy,
        "avg_delay_s": avg_delay,
        **{f"energy_class_{cls}_J": val for cls, val in energy_class.items()},
        "collision_distribution": collision_dist,
        "collisions": collisions,
    }


def _load_sca_file(path: Path) -> dict[str, Any]:
    """Parse a single ``.sca`` file and compute aggregated metrics."""
    if pd is None:
        reference = load_reference_metrics(path)
        extras = _aggregate_rows_no_pandas([_parse_sca_file(path)])
        metrics = _metrics_from_reference(reference)
        metrics.update(extras)
        return metrics
    row = _parse_sca_file(path)
    df = pd.DataFrame([row])
    return _aggregate_df(df)


def load_flora_metrics(path: str | Path) -> dict[str, Any]:
    """Return metrics from a FLoRa export.

    The path can point to a CSV converted from the original ``.sca``/``.vec``
    files produced by OMNeT++. The CSV is expected to contain at least the
    columns ``sent`` and ``received`` to compute the PDR as well as ``sfX``
    columns describing the spreading factor distribution. Additional optional
    columns may be present:

    ``throughput_bps``
        Average throughput in bits per second.
    ``energy`` or ``energy_J``
        Energy consumption for the run.
    ``collisions``
        Total number of packet collisions.
    ``collisions_sfX``
        Number of collisions that occurred with spreading factor ``X``.
    """
    if pd is None:
        path = Path(path)
        reference = load_reference_metrics(path)
        if path.is_dir():
            rows = [_parse_sca_file(p) for p in sorted(path.glob("*.sca"))]
        elif path.suffix.lower() == ".sca":
            rows = [_parse_sca_file(path)]
        else:
            rows = _read_csv_rows(path)
        extras = _aggregate_rows_no_pandas(rows)
        metrics = _metrics_from_reference(reference)
        metrics.update(extras)
        return metrics
    path = Path(path)
    if path.is_dir():
        rows = [_parse_sca_file(p) for p in sorted(path.glob("*.sca"))]
        df = pd.DataFrame(rows)
        return _aggregate_df(df)

    if path.suffix.lower() == ".sca":
        return _load_sca_file(path)

    df = pd.read_csv(path)
    total_sent = int(df["sent"].sum()) if "sent" in df.columns else 0
    total_recv = int(df["received"].sum()) if "received" in df.columns else 0
    pdr = total_recv / total_sent if total_sent else 0.0
    sf_cols = [
        c
        for c in df.columns
        if c.startswith("sf") and not c.startswith("collisions_sf")
    ]
    sf_hist = {int(c[2:]): int(df[c].sum()) for c in sf_cols}

    throughput = (
        float(df["throughput_bps"].mean()) if "throughput_bps" in df.columns else 0.0
    )
    avg_delay = float(df["avg_delay_s"].mean()) if "avg_delay_s" in df.columns else 0.0
    if "energy_J" in df.columns:
        energy = float(df["energy_J"].mean())
    elif "energy" in df.columns:
        energy = float(df["energy"].mean())
    else:
        energy = 0.0

    collisions = int(df["collisions"].sum()) if "collisions" in df.columns else 0

    collision_cols = [c for c in df.columns if c.startswith("collisions_sf")]
    collision_dist = {int(c.split("sf")[1]): int(df[c].sum()) for c in collision_cols}
    energy_class = {
        col.split("_")[2]: float(df[col].mean())
        for col in df.columns
        if col.startswith("energy_class_")
    }

    return {
        "PDR": pdr,
        "sf_distribution": sf_hist,
        "throughput_bps": throughput,
        "energy_J": energy,
        "avg_delay_s": avg_delay,
        **{f"energy_class_{cls}_J": val for cls, val in energy_class.items()},
        "collision_distribution": collision_dist,
        "collisions": collisions,
    }


def compare_with_sim(
    sim_metrics: dict[str, Any], flora_csv: str | Path, *, pdr_tol: float = 0.05
) -> bool:
    """Compare simulator metrics with FLoRa results.

    Parameters
    ----------
    sim_metrics : dict
        Metrics returned by :meth:`Simulator.get_metrics`.
    flora_csv : str | Path
        Path to the FLoRa CSV export to compare against.
    pdr_tol : float, optional
        Accepted absolute tolerance on the PDR difference. Defaults to ``0.05``.

    Returns
    -------
    bool
        ``True`` if the metrics match within tolerance.
    """
    flora_metrics = load_flora_metrics(flora_csv)
    pdr_match = abs(sim_metrics.get("PDR", 0.0) - flora_metrics["PDR"]) <= pdr_tol
    sf_match = sim_metrics.get("sf_distribution") == flora_metrics["sf_distribution"]
    return pdr_match and sf_match


def replay_flora_txconfig(
    sim: "Simulator", events: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Replay a FLoRa TXCONFIG trace and compare ADR decisions.

    Parameters
    ----------
    sim:
        Simulator instance configured like the target scenario.
    events:
        Iterable describing the FLoRa TXCONFIG reference trace.

    Returns
    -------
    dict
        Structured report with per-event decisions, detected mismatches,
        throttled events and the final node state.
    """

    apply_adr_standard(sim)
    node = sim.nodes[0]
    server = sim.network_server

    server.scheduler.queue.clear()

    mismatches: list[dict[str, Any]] = []
    throttled_events: list[int] = []
    results: list[dict[str, Any]] = []

    last_expected_sf = node.sf
    last_expected_power = node.tx_power

    for entry in events:
        event_id = int(entry["event_id"])
        best_gateway = int(entry["best_gateway"])
        gateways = entry["gateways"]
        best_info = gateways[str(best_gateway)]
        end_time = float(entry["end_time"])

        frames_before = getattr(node, "frames_since_last_adr_command", 0)
        adr_ack_req = getattr(node, "last_adr_ack_req", False)

        sim.current_time = end_time
        for gw_id_str, info in sorted(
            gateways.items(), key=lambda item: int(item[0]), reverse=True
        ):
            gw_id = int(gw_id_str)
            server.receive(
                event_id,
                node.id,
                gw_id,
                info.get("rssi"),
                end_time=end_time,
                snir=info.get("snr"),
            )

        recorded = node.gateway_snr_history.get(best_gateway, [])
        recorded_snr = recorded[-1] if recorded else None
        if recorded_snr is None:
            mismatches.append(
                {
                    "event_id": event_id,
                    "type": "missing_best_gateway_history",
                    "expected": best_info["snr"],
                    "observed": recorded,
                }
            )
        elif recorded_snr != best_info["snr"]:
            mismatches.append(
                {
                    "event_id": event_id,
                    "type": "best_gateway_snr_mismatch",
                    "expected": best_info["snr"],
                    "observed": recorded_snr,
                }
            )

        expected = entry.get("expected_command")
        decision: dict[str, Any] | None = None
        throttled = False

        queue = server.scheduler.queue.get(node.id)

        if expected:
            if not queue:
                if frames_before < ADR_WINDOW_SIZE and not adr_ack_req:
                    throttled = True
                    throttled_events.append(event_id)
                else:
                    mismatches.append(
                        {
                            "event_id": event_id,
                            "type": "missing_downlink",
                            "details": {
                                "frames_since_command": frames_before,
                                "adr_ack_req": adr_ack_req,
                            },
                        }
                    )
            else:
                scheduled_time = queue[0][0]
                if not math.isclose(
                    scheduled_time,
                    expected["downlink_time"],
                    rel_tol=0.0,
                    abs_tol=1e-6,
                ):
                    mismatches.append(
                        {
                            "event_id": event_id,
                            "type": "downlink_time_mismatch",
                            "expected": expected["downlink_time"],
                            "observed": scheduled_time,
                        }
                    )
                ready = server.scheduler.pop_ready(
                    node.id, expected["downlink_time"] + 1e-6
                )
                if ready is None:
                    mismatches.append(
                        {
                            "event_id": event_id,
                            "type": "downlink_not_ready",
                            "expected": expected,
                        }
                    )
                else:
                    frame = ready.frame
                    gateway = ready.gateway
                    req = LinkADRReq.from_bytes(frame.payload[:5])
                    decided_sf = DR_TO_SF[req.datarate]
                    decided_power = TX_POWER_INDEX_TO_DBM[req.tx_power]
                    decision = {
                        "sf": decided_sf,
                        "tx_power": decided_power,
                        "gateway_id": gateway.id,
                        "downlink_time": scheduled_time,
                    }
                    if decided_sf != expected["sf"] or decided_power != expected["tx_power"]:
                        mismatches.append(
                            {
                                "event_id": event_id,
                                "type": "command_mismatch",
                                "expected": expected,
                                "observed": decision,
                            }
                        )
                    elif gateway.id != expected["gateway_id"]:
                        mismatches.append(
                            {
                                "event_id": event_id,
                                "type": "gateway_mismatch",
                                "expected": expected["gateway_id"],
                                "observed": gateway.id,
                            }
                        )
                    node.handle_downlink(frame)
                    last_expected_sf = decided_sf
                    last_expected_power = decided_power
        else:
            if queue:
                mismatches.append(
                    {
                        "event_id": event_id,
                        "type": "unexpected_downlink",
                        "details": queue,
                    }
                )

        results.append(
            {
                "event_id": event_id,
                "expected": expected,
                "decision": decision,
                "throttled": throttled,
                "recorded_snr": recorded_snr,
                "best_gateway": best_gateway,
            }
        )

    final_state = {"sf": node.sf, "tx_power": node.tx_power}
    if node.sf != last_expected_sf or node.tx_power != last_expected_power:
        mismatches.append(
            {
                "event_id": None,
                "type": "final_state_mismatch",
                "expected": {
                    "sf": last_expected_sf,
                    "tx_power": last_expected_power,
                },
                "observed": final_state,
            }
        )

    return {
        "results": results,
        "mismatches": mismatches,
        "throttled_events": throttled_events,
        "final_state": final_state,
    }


def load_flora_rx_stats(path: str | Path) -> dict[str, Any]:
    """Load average RSSI/SNR and collisions from a FLoRa export."""
    if pd is None:
        path = Path(path)
        if path.is_dir():
            rows = [_parse_sca_file(p) for p in sorted(path.glob("*.sca"))]
        elif path.suffix.lower() == ".sca":
            rows = [_parse_sca_file(path)]
        else:
            rows = _read_csv_rows(path)

        rssi_values = [float(row["rssi"]) for row in rows if "rssi" in row]
        snr_values = [float(row["snr"]) for row in rows if "snr" in row]
        collisions = sum(int(row["collisions"]) for row in rows if "collisions" in row)

        avg_rssi = sum(rssi_values) / len(rssi_values) if rssi_values else 0.0
        avg_snr = sum(snr_values) / len(snr_values) if snr_values else 0.0

        return {"rssi": avg_rssi, "snr": avg_snr, "collisions": collisions}
    path = Path(path)
    if path.is_dir():
        rows = [_parse_sca_file(p) for p in sorted(path.glob("*.sca"))]
        df = pd.DataFrame(rows)
    elif path.suffix.lower() == ".sca":
        df = pd.DataFrame([_parse_sca_file(path)])
    else:
        df = pd.read_csv(path)

    rssi = float(df["rssi"].mean()) if "rssi" in df.columns else 0.0
    snr = float(df["snr"].mean()) if "snr" in df.columns else 0.0
    collisions = int(df["collisions"].sum()) if "collisions" in df.columns else 0
    return {"rssi": rssi, "snr": snr, "collisions": collisions}
