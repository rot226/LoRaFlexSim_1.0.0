"""Plot total or per-node energy consumption from CSV files."""
import sys
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def main(
    files: list[str],
    per_node: bool,
    output_dir: Path,
    basename: str | None,
) -> None:
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    if per_node:
        cols = [c for c in df.columns if c.startswith("energy_by_node.")]
        if not cols:
            print("No per-node consumption columns found.")
            return
        energy = {int(c.split(".")[1]): df[c].mean() for c in cols}
        nodes = sorted(energy)
        values = [energy[n] for n in nodes]
        plt.bar(nodes, values)
        plt.xlabel("Node")
        plt.ylabel("Energy consumed (J)")
        plt.grid(True)
        if basename is None:
            basename = "energy_per_node"
    else:
        col = "energy_J" if "energy_J" in df.columns else "energy"
        if col not in df.columns:
            print("No energy_J or energy column found.")
            return
        if "nodes" in df.columns:
            series = df.groupby("nodes")[col].mean()
            series.plot(marker="o")
            plt.xlabel("Number of nodes")
        else:
            series = df[col]
            series.plot(marker="o")
            plt.xlabel("Run")
        plt.ylabel("Energy consumed (J)")
        plt.grid(True)
        if basename is None:
            basename = "energy_total"
    plt.tight_layout()
    for ext, params in {"png": {"dpi": 300}, "jpg": {"dpi": 300}, "eps": {}}.items():
        path = output_dir / f"{basename}.{ext}"
        plt.savefig(path, **params)
        print(f"Figure saved to {path}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot energy consumption and save the figure as PNG, JPG and EPS",
    )
    parser.add_argument("files", nargs="+", help="Metrics CSV files")
    parser.add_argument(
        "--per-node",
        action="store_true",
        help="Plot consumption per node",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Output directory (default: current folder)",
    )
    parser.add_argument(
        "--basename",
        default=None,
        help="Base filename without extension. Defaults to 'energy_total' or 'energy_per_node' depending on --per-node",
    )
    return parser.parse_args(argv)

if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args.files, args.per_node, args.output_dir, args.basename)

