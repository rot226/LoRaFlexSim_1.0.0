#!/usr/bin/env python3
"""Plot PDR against noise standard deviation."""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

# Allow running the script from a clone without installation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"


def main() -> None:
    summary_file = RESULTS_DIR / "noise_summary.csv"
    pdr_map: dict[float, list[float]] = defaultdict(list)
    with summary_file.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            ns = float(row["noise_std"])
            pdr_map[ns].append(float(row["PDR(%)"]))

    noise_levels = sorted(pdr_map.keys())
    mean_pdr = [sum(pdr_map[ns]) / len(pdr_map[ns]) for ns in noise_levels]

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots()
    ax.plot(noise_levels, mean_pdr, marker="o")
    ax.set_xlabel("noise_std")
    ax.set_ylabel("PDR(%)")
    ax.set_title("PDR vs Noise")
    output_path = FIGURES_DIR / "pdr_vs_noise.png"
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
