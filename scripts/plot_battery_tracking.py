"""Plot battery evolution from ``results/battery_tracking.csv``.

The CSV is expected to contain columns ``time``, ``node_id`` and ``energy_j`` as
produced by ``run_battery_tracking.py``.  This utility draws the remaining energy
of each node over time and also plots the average across nodes.  The figure is
saved to ``figures/battery_tracking.png``.

Usage::

    python scripts/plot_battery_tracking.py
"""

from __future__ import annotations

import os
import sys

# Allow running the script from a clone without installation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:  # pandas and matplotlib are optional but required for plotting
    import pandas as pd
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(f"Required plotting libraries missing: {exc}")

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "figures")


def main() -> None:
    in_path = os.path.join(RESULTS_DIR, "battery_tracking.csv")
    if not os.path.exists(in_path):
        raise SystemExit(f"Input file not found: {in_path}")

    df = pd.read_csv(in_path)
    if not {"time", "node_id", "energy_j"} <= set(df.columns):
        raise SystemExit("CSV must contain time, node_id and energy_j columns")

    plt.figure()
    for node_id, group in df.groupby("node_id"):
        plt.plot(group["time"], group["energy_j"], label=f"Node {node_id}")

    avg = df.groupby("time")["energy_j"].mean()
    plt.plot(avg.index, avg.values, color="k", linewidth=2, label="Average")

    plt.xlabel("Time (s)")
    plt.ylabel("Energy (J)")
    plt.grid(True)
    plt.legend()

    os.makedirs(FIGURES_DIR, exist_ok=True)
    out_path = os.path.join(FIGURES_DIR, "battery_tracking.png")
    plt.savefig(out_path)
    print(f"Saved {out_path}")


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
