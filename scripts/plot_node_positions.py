#!/usr/bin/env python3
"""Plot the initial positions of simulated nodes."""

from __future__ import annotations

import os
import sys
import argparse
from pathlib import Path

import matplotlib.pyplot as plt

# Allow running the script from a clone without installation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from simulateur_lora_sfrd.launcher.simulator import Simulator


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--num-nodes", type=int, default=100, help="Number of nodes to simulate"
    )
    parser.add_argument(
        "--area-size", type=float, default=1000.0, help="Side of the square area"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--output",
        default="figures/node_positions.png",
        help="Path to save the scatter plot",
    )
    args = parser.parse_args(argv)

    sim = Simulator(
        num_nodes=args.num_nodes,
        area_size=args.area_size,
        seed=args.seed,
        mobility=False,
    )

    positions = [(n.x, n.y) for n in sim.nodes]
    xs, ys = zip(*positions)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure()
    plt.scatter(xs, ys)
    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Node positions")
    plt.savefig(output_path)
    plt.close()


if __name__ == "__main__":
    main()
