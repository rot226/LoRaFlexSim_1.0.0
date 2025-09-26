#!/usr/bin/env python3
"""Run the validation matrix scenarios and compare against FLoRa baselines."""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path
from typing import Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from loraflexsim.validation import (
    SCENARIOS,
    compare_to_reference,
    load_flora_reference,
    run_validation,
)


def run_matrix(output: Path, repeat: int) -> bool:
    """Execute all validation scenarios and persist a summary CSV."""

    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, float | str]] = []
    overall_success = True

    for scenario in SCENARIOS:
        run_count = repeat if scenario.name == "long_range" else 1
        metrics_runs: list[dict[str, float]] = []
        for idx in range(run_count):
            overrides: dict[str, float | int | None] = {}
            if scenario.name == "long_range" and run_count > 1:
                base_seed = scenario.sim_kwargs.get("seed")
                if base_seed is not None:
                    overrides["seed"] = int(base_seed) + idx
            sim = scenario.build_simulator(**overrides)
            metrics_runs.append(run_validation(sim, scenario.run_steps))

        metrics = {
            key: sum(run[key] for run in metrics_runs) / len(metrics_runs)
            for key in metrics_runs[0]
        }
        pdr_std = (
            statistics.pstdev(run["PDR"] for run in metrics_runs)
            if len(metrics_runs) > 1
            else 0.0
        )
        reference = load_flora_reference(scenario.flora_reference)
        deltas = compare_to_reference(metrics, reference, scenario.tolerances)

        status = (
            deltas["PDR"] <= scenario.tolerances.pdr
            and deltas["collisions"] <= scenario.tolerances.collisions
            and deltas["snr"] <= scenario.tolerances.snr
        )
        overall_success &= status

        rows.append(
            {
                "scenario": scenario.name,
                "description": scenario.description,
                "pdr_sim": metrics["PDR"],
                "pdr_ref": reference["PDR"],
                "pdr_delta": deltas["PDR"],
                "pdr_std": pdr_std,
                "collisions_sim": metrics["collisions"],
                "collisions_ref": reference["collisions"],
                "collisions_delta": deltas["collisions"],
                "snr_sim": metrics["snr"],
                "snr_ref": reference["snr"],
                "snr_delta": deltas["snr"],
                "tolerance_pdr": scenario.tolerances.pdr,
                "tolerance_collisions": scenario.tolerances.collisions,
                "tolerance_snr": scenario.tolerances.snr,
                "status": "ok" if status else "fail",
            }
        )

    fieldnames: Sequence[str] = rows[0].keys() if rows else []
    with output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        pdr_value = f"{row['pdr_sim']:.3f}"
        if row.get("pdr_std", 0.0):
            pdr_value += f"±{row['pdr_std']:.3f}"
        print(
            f"{row['scenario']}: PDR={pdr_value} (ref {row['pdr_ref']:.3f}, Δ{row['pdr_delta']:.3f}) | "
            f"Collisions={row['collisions_sim']:.1f} (ref {row['collisions_ref']:.1f}, Δ{row['collisions_delta']:.1f}) | "
            f"SNR={row['snr_sim']:.2f} dB (ref {row['snr_ref']:.2f}, Δ{row['snr_delta']:.2f}) -> {row['status']}"
        )

    print(f"Summary written to {output}")
    return overall_success


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/validation_matrix.csv"),
        help="Destination CSV file for the summary table.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help=(
            "Nombre d'exécutions pour le scénario long_range afin de calculer la "
            "moyenne et l'écart-type du PDR."
        ),
    )
    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat doit être supérieur ou égal à 1")

    try:
        success = run_matrix(args.output, args.repeat)
    except RuntimeError as exc:  # pragma: no cover - propagates optional deps errors
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0 if success else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
