"""Plot PDR and collisions as a function of channel count.

This utility reads ``results/channels_summary.csv`` produced by
``run_channels_sweep.py`` and plots the average packet delivery ratio and
collisions for each number of channels.  The figure is saved to
``figures/pdr_collisions_vs_channels.png``.

Usage::

    python scripts/plot_channels_sweep.py
"""

from __future__ import annotations

import argparse
import os
import sys

try:  # pandas and matplotlib are optional but required for plotting
    import pandas as pd
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(f"Required plotting libraries missing: {exc}")

from loraflexsim.utils.plotting import parse_formats, save_multi_format

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "figures")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--formats",
        default="png,jpg,eps",
        help="Comma-separated list of output formats",
    )
    args = parser.parse_args(argv or [])

    in_path = os.path.join(RESULTS_DIR, "channels_summary.csv")
    if not os.path.exists(in_path):
        raise SystemExit(f"Input file not found: {in_path}")

    df = pd.read_csv(in_path)
    required = {"channels", "PDR(%)", "collisions"}
    if not required <= set(df.columns):
        raise SystemExit("CSV must contain channels, PDR(%) and collisions columns")

    stats = df.groupby("channels")[["PDR(%)", "collisions"]].mean().reset_index()

    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()

    ax1.plot(stats["channels"], stats["PDR(%)"], marker="o", color="C0")
    ax2.plot(stats["channels"], stats["collisions"], marker="s", color="C1")

    ax1.set_xlabel("channels")
    ax1.set_ylabel("PDR(%)", color="C0")
    ax2.set_ylabel("collisions", color="C1")
    ax1.tick_params(axis="y", labelcolor="C0")
    ax2.tick_params(axis="y", labelcolor="C1")

    fig.tight_layout()
    os.makedirs(FIGURES_DIR, exist_ok=True)
    base = os.path.join(FIGURES_DIR, "pdr_collisions_vs_channels")
    save_multi_format(fig, base, parse_formats(args.formats))


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
