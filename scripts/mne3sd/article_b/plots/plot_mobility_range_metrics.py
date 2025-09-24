"""Plot mobility range metrics for the MNE3SD article B analysis."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
RESULTS_PATH = ROOT / "results" / "mne3sd" / "article_b" / "mobility_range_metrics.csv"
FIGURES_DIR = ROOT / "figures" / "mne3sd" / "article_b"


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
            "Generate mobility range plots showing the PDR and average delay "
            "versus communication range for each mobility model."
        )
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=RESULTS_PATH,
        help="Path to the mobility_range_metrics.csv file",
    )
    parser.add_argument(
        "--style",
        help="Matplotlib style name or .mplstyle path to override the default settings",
    )
    parser.add_argument(
        "--highlight-threshold",
        type=float,
        help=(
            "Highlight communication ranges whose aggregated PDR (in %) falls below this "
            "threshold, e.g. 90 for 90%."
        ),
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the figures instead of running in batch mode",
    )
    return parser.parse_args()


def load_metrics(path: Path) -> pd.DataFrame:
    """Return the aggregated metrics needed for plotting."""

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("No rows found in the metrics CSV")

    required_columns = {
        "model",
        "range_km",
        "replicate",
        "pdr_mean",
        "pdr_std",
        "avg_delay_s_mean",
        "avg_delay_s_std",
    }
    missing = required_columns.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"Missing required columns: {missing_cols}")

    aggregated = df[df["replicate"] == "aggregate"].copy()
    if aggregated.empty:
        raise ValueError("No aggregated rows (replicate == 'aggregate') found in metrics CSV")

    aggregated["model"] = aggregated["model"].astype(str)
    aggregated["range_km"] = aggregated["range_km"].astype(float)
    aggregated["pdr_mean"] = aggregated["pdr_mean"].astype(float) * 100.0
    aggregated["pdr_std"] = aggregated["pdr_std"].astype(float) * 100.0
    aggregated["avg_delay_s_mean"] = aggregated["avg_delay_s_mean"].astype(float)
    aggregated["avg_delay_s_std"] = aggregated["avg_delay_s_std"].astype(float)

    return aggregated


def plot_pdr_vs_range(
    df: pd.DataFrame, output_dir: Path, highlight_threshold: float | None
) -> None:
    """Plot aggregated PDR versus communication range with error bars."""

    fig, ax = plt.subplots()
    highlight_label_added = False

    for model_name, model_data in df.groupby("model"):
        ordered = model_data.sort_values("range_km")
        ax.errorbar(
            ordered["range_km"],
            ordered["pdr_mean"],
            yerr=ordered["pdr_std"],
            marker="o",
            capsize=3,
            label=model_name.replace("_", " ").title(),
        )

        if highlight_threshold is not None:
            mask = ordered["pdr_mean"] < highlight_threshold
            if mask.any():
                highlight_points = ordered[mask]
                label = "PDR below threshold" if not highlight_label_added else None
                ax.scatter(
                    highlight_points["range_km"],
                    highlight_points["pdr_mean"],
                    color="tab:red",
                    marker="s",
                    s=36,
                    edgecolor="white",
                    linewidths=0.6,
                    label=label,
                    zorder=3,
                )
                highlight_label_added = True

    ax.set_xlabel("Communication range (km)")
    ax.set_ylabel("PDR (%)")
    ax.set_title("PDR versus communication range")
    ax.set_ylim(0, 105)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.legend()
    fig.tight_layout()

    save_figure(fig, output_dir / "pdr_vs_communication_range")


def plot_delay_vs_range(df: pd.DataFrame, output_dir: Path) -> None:
    """Plot aggregated average delay versus communication range."""

    fig, ax = plt.subplots()

    for model_name, model_data in df.groupby("model"):
        ordered = model_data.sort_values("range_km")
        ax.plot(
            ordered["range_km"],
            ordered["avg_delay_s_mean"],
            marker="o",
            label=model_name.replace("_", " ").title(),
        )

    ax.set_xlabel("Communication range (km)")
    ax.set_ylabel("Average delay (s)")
    ax.set_title("Average delay versus communication range")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.legend()
    fig.tight_layout()

    save_figure(fig, output_dir / "average_delay_vs_communication_range")


def save_figure(fig: plt.Figure, base_path: Path) -> None:
    """Save ``fig`` to ``base_path`` as PNG and EPS files."""

    base_path.parent.mkdir(parents=True, exist_ok=True)
    png_path = base_path.with_suffix(".png")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    print(f"Saved {png_path}")
    eps_path = base_path.with_suffix(".eps")
    fig.savefig(eps_path, dpi=300, format="eps", bbox_inches="tight")
    print(f"Saved {eps_path}")


def main() -> None:  # pragma: no cover - CLI entry point
    args = parse_arguments()

    apply_plot_style(args.style)

    metrics = load_metrics(args.results)

    plot_pdr_vs_range(metrics, FIGURES_DIR, args.highlight_threshold)
    plot_delay_vs_range(metrics, FIGURES_DIR)

    if args.show:
        plt.show()
    else:
        plt.close("all")


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
