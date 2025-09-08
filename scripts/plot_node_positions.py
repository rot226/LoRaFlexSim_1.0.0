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
from loraflexsim.launcher.simulator import Simulator
from loraflexsim.utils.plotting import configure_style


configure_style()


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
    parser.add_argument(
        "--marker-size",
        type=float,
        default=100.0,
        help="Marker size for node positions",
    )
    parser.add_argument(
        "--style", help="Matplotlib style to apply (overrides MPLSTYLE)"
    )
    args = parser.parse_args(argv)
    configure_style(args.style)

    sim = Simulator(
        num_nodes=args.num_nodes,
        area_size=args.area_size,
        seed=args.seed,
        mobility=False,
    )
    positions = [(n.x, n.y) for n in sim.nodes]
    xs, ys = zip(*positions)

    gateway_positions = [(g.x, g.y) for g in sim.gateways]
    gx, gy = (zip(*gateway_positions) if gateway_positions else ([], []))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots()
    ax.scatter(xs, ys, s=args.marker_size, edgecolors="black", facecolors="C0")
    for n in sim.nodes:
        ax.annotate(
            str(n.id),
            (n.x, n.y),
            ha="center",
            va="center",
            fontsize=8,
            color="white",
        )

    if gateway_positions:
        ax.scatter(
            gx,
            gy,
            marker="*",
            s=200,
            edgecolors="black",
            facecolors="red",
        )
        for g in sim.gateways:
            ax.annotate(
                str(g.id),
                (g.x, g.y),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
            )

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Node positions")
    for ext in (".png", ".jpg", ".eps"):
        dpi = 300 if ext in (".png", ".jpg") else None
        fig.savefig(output_path.with_suffix(ext), dpi=dpi)
    plt.close(fig)


if __name__ == "__main__":
    main()
