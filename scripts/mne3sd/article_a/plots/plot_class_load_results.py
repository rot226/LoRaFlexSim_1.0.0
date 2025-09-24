"""Plot class load metrics for MNE3SD article A analysis."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
RESULTS_PATH = ROOT / "results" / "mne3sd" / "article_a" / "class_load_metrics.csv"
FIGURES_DIR = ROOT / "figures" / "mne3sd" / "article_a"


def apply_plot_style(style: str | None) -> None:
    """Apply the default IEEE-inspired plotting style unless overridden."""
    plt.rcdefaults()
    if style:
        plt.style.use(style)
        return

    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 7,
            "figure.figsize": (3.5, 2.2),
        }
    )


def parse_arguments() -> argparse.Namespace:
    """Return the parsed command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate plots for class load simulations, showing average energy per "
            "node and packet delivery ratio versus reporting interval."
        )
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=RESULTS_PATH,
        help="Path to the class_load_metrics.csv file",
    )
    parser.add_argument(
        "--style",
        help="Matplotlib style name or .mplstyle path to override the default settings",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the figures instead of running in batch mode",
    )
    return parser.parse_args()


def load_metrics(path: Path) -> pd.DataFrame:
    """Read the metrics CSV, ensuring mandatory columns are present."""
    df = pd.read_csv(path)
    required = {
        "class",
        "interval_s",
        "energy_per_node_J",
        "pdr",
    }
    missing = required.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"Missing required columns: {missing_cols}")
    df["interval_s"] = df["interval_s"].astype(float)
    df["energy_per_node_J"] = df["energy_per_node_J"].astype(float)
    df["pdr"] = df["pdr"].astype(float)
    return df


def plot_energy_by_interval(df: pd.DataFrame, output_dir: Path) -> None:
    """Plot the average per-node energy versus interval for each class."""
    grouped = (
        df.groupby(["class", "interval_s"], as_index=False)["energy_per_node_J"].mean()
    )

    fig, ax = plt.subplots()

    for class_name, class_data in grouped.groupby("class"):
        ordered = class_data.sort_values("interval_s")
        ax.plot(
            ordered["interval_s"],
            ordered["energy_per_node_J"],
            marker="o",
            label=f"Class {class_name}",
        )

    ax.set_xlabel("Reporting interval (s)")
    ax.set_ylabel("Average energy per node (J)")
    ax.set_title("Average energy consumption per class")
    ax.legend(title="Class")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    fig.tight_layout()

    save_figure(fig, output_dir / "class_energy_vs_interval")


def plot_pdr_by_interval(df: pd.DataFrame, output_dir: Path) -> None:
    """Plot the packet delivery ratio versus interval with error bars."""
    stats = (
        df.groupby(["class", "interval_s"], as_index=False)["pdr"]
        .agg(["mean", "std"])
        .reset_index()
    )
    stats.rename(columns={"mean": "pdr_mean", "std": "pdr_std"}, inplace=True)
    stats["pdr_mean"] *= 100.0
    stats["pdr_std"] = stats["pdr_std"].fillna(0.0) * 100.0

    fig, ax = plt.subplots()

    for class_name, class_data in stats.groupby("class"):
        ordered = class_data.sort_values("interval_s")
        ax.errorbar(
            ordered["interval_s"],
            ordered["pdr_mean"],
            yerr=ordered["pdr_std"],
            marker="o",
            capsize=3,
            label=f"Class {class_name}",
        )

    ax.set_xlabel("Reporting interval (s)")
    ax.set_ylabel("PDR (%)")
    ax.set_title("Packet delivery ratio per class")
    ax.set_ylim(0, 105)
    ax.legend(title="Class")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    fig.tight_layout()

    save_figure(fig, output_dir / "class_pdr_vs_interval")


def save_figure(fig: plt.Figure, base_path: Path) -> None:
    """Save ``fig`` to ``base_path`` as PNG and EPS files."""
    base_path.parent.mkdir(parents=True, exist_ok=True)
    png_path = base_path.with_suffix(".png")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    print(f"Saved {png_path}")
    eps_path = base_path.with_suffix(".eps")
    fig.savefig(eps_path, dpi=300, format="eps", bbox_inches="tight")
    print(f"Saved {eps_path}")


def main() -> None:
    args = parse_arguments()

    apply_plot_style(args.style)

    metrics = load_metrics(args.results)

    plot_energy_by_interval(metrics, FIGURES_DIR)
    plot_pdr_by_interval(metrics, FIGURES_DIR)

    if args.show:
        plt.show()
    else:
        plt.close("all")


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
