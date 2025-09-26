"""Plot mobility gateway metrics for the MNE3SD article B analysis."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, os.fspath(ROOT))

from scripts.mne3sd.common import (  # noqa: E402
    apply_ieee_style,
    prepare_figure_directory,
    save_figure,
)

RESULTS_PATH = (
    ROOT
    / "results"
    / "mne3sd"
    / "article_b"
    / "mobility_gateway_metrics.csv"
)
ARTICLE = "article_b"
SCENARIO = "mobility_gateway"


def parse_arguments() -> argparse.Namespace:
    """Return the parsed command line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate mobility gateway plots showing the PDR distribution per gateway, "
            "downlink latency improvements when adding gateways, and a comparison "
            "between RandomWaypoint and Smooth trajectories."
        )
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=RESULTS_PATH,
        help="Path to the mobility_gateway_metrics.csv file",
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


def parse_gateway_distribution(value: object) -> dict[str, float]:
    """Return a parsed gateway distribution from a JSON encoded string."""

    if isinstance(value, dict):
        return {str(key): float(val) for key, val in value.items()}
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive programming
        raise ValueError(f"Invalid gateway distribution payload: {value!r}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            "Gateway distribution must decode to an object mapping gateway IDs to ratios"
        )
    return {str(key): float(val) for key, val in parsed.items()}


def load_metrics(path: Path) -> pd.DataFrame:
    """Return the aggregated metrics needed for plotting."""

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("No rows found in the metrics CSV")

    required_columns = {
        "model",
        "gateways",
        "replicate",
        "pdr_mean",
        "pdr_std",
        "avg_downlink_delay_s_mean",
        "avg_downlink_delay_s_std",
        "pdr_by_gateway_mean",
    }
    missing = required_columns.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"Missing required columns: {missing_cols}")

    aggregated = df[df["replicate"] == "aggregate"].copy()
    if aggregated.empty:
        raise ValueError("No aggregated rows (replicate == 'aggregate') found in metrics CSV")

    aggregated["model"] = aggregated["model"].astype(str)
    aggregated["gateways"] = aggregated["gateways"].astype(int)
    aggregated["pdr_mean"] = aggregated["pdr_mean"].astype(float) * 100.0
    aggregated["pdr_std"] = aggregated["pdr_std"].astype(float) * 100.0
    aggregated["avg_downlink_delay_s_mean"] = aggregated["avg_downlink_delay_s_mean"].astype(float)
    aggregated["avg_downlink_delay_s_std"] = aggregated["avg_downlink_delay_s_std"].astype(float)
    aggregated["pdr_distribution"] = aggregated["pdr_by_gateway_mean"].apply(
        parse_gateway_distribution
    )

    return aggregated


def ordered_gateway_ids(distributions: Iterable[dict[str, float]]) -> list[str]:
    """Return a sorted list of gateway identifiers from all distributions."""

    ids: set[str] = set()
    for distribution in distributions:
        for key in distribution:
            ids.add(str(key))
    try:
        return [str(identifier) for identifier in sorted(ids, key=lambda x: int(x))]
    except ValueError:
        return sorted(ids)


def plot_pdr_distribution_by_gateway(df: pd.DataFrame) -> None:
    """Plot the share of uplink deliveries handled by each gateway."""

    entries: list[dict[str, object]] = []
    for row in df.itertuples():
        distribution = getattr(row, "pdr_distribution", {})
        if not distribution:
            continue
        total = sum(distribution.values())
        shares = {
            key: (value / total * 100.0 if total else 0.0)
            for key, value in distribution.items()
        }
        label = f"{row.model.replace('_', ' ').title()} – {row.gateways} GW"
        entries.append({"label": label, "shares": shares})

    if not entries:
        raise ValueError("No gateway distribution data available for plotting")

    gateway_ids = ordered_gateway_ids(entry["shares"] for entry in entries)
    fig, ax = plt.subplots()
    indices = range(len(entries))
    bottoms = [0.0] * len(entries)

    for gateway_id in gateway_ids:
        heights = [entry["shares"].get(gateway_id, 0.0) for entry in entries]
        ax.bar(indices, heights, bottom=bottoms, label=f"Gateway {gateway_id}")
        bottoms = [bottom + height for bottom, height in zip(bottoms, heights)]

    ax.set_xticks(list(indices), [entry["label"] for entry in entries], rotation=30, ha="right")
    ax.set_ylabel("PDR share (%)")
    ax.set_title("PDR distribution by gateway")
    ax.set_ylim(0, 100)
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.legend(title="Gateways")
    fig.tight_layout()

    output_dir = prepare_figure_directory(
        article=ARTICLE,
        scenario=SCENARIO,
        metric="pdr_distribution_by_gateway",
    )
    save_figure(fig, "pdr_distribution_by_gateway", output_dir)


def plot_downlink_delay_vs_gateways(df: pd.DataFrame) -> None:
    """Plot the average downlink delay versus the number of gateways."""

    fig, ax = plt.subplots()

    for model_name, model_data in df.groupby("model"):
        ordered = model_data.sort_values("gateways")
        ax.errorbar(
            ordered["gateways"],
            ordered["avg_downlink_delay_s_mean"],
            yerr=ordered["avg_downlink_delay_s_std"],
            marker="o",
            capsize=3,
            label=model_name.replace("_", " ").title(),
        )

    ax.set_xlabel("Number of gateways")
    ax.set_ylabel("Average downlink delay (s)")
    ax.set_title("Impact of the number of gateways on downlink delay")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.legend()
    fig.tight_layout()

    output_dir = prepare_figure_directory(
        article=ARTICLE,
        scenario=SCENARIO,
        metric="downlink_delay_vs_gateways",
    )
    save_figure(fig, "average_downlink_delay_vs_gateways", output_dir)


def plot_model_comparison(df: pd.DataFrame) -> None:
    """Plot a scatter chart comparing mobility models on PDR and downlink delay."""

    fig, ax = plt.subplots()

    markers = {"random_waypoint": "o", "smooth": "s"}
    for model_name, model_data in df.groupby("model"):
        marker = markers.get(model_name, "o")
        ax.scatter(
            model_data["pdr_mean"],
            model_data["avg_downlink_delay_s_mean"],
            label=model_name.replace("_", " ").title(),
            marker=marker,
            s=40,
        )
        for row in model_data.itertuples():
            ax.annotate(
                f"{row.gateways} GW",
                (row.pdr_mean, row.avg_downlink_delay_s_mean),
                textcoords="offset points",
                xytext=(4, -6),
                fontsize=6,
            )

    ax.set_xlabel("Aggregated PDR (%)")
    ax.set_ylabel("Average downlink delay (s)")
    ax.set_title("RandomWaypoint vs Smooth comparison")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.legend()
    fig.tight_layout()

    output_dir = prepare_figure_directory(
        article=ARTICLE,
        scenario=SCENARIO,
        metric="model_comparison",
    )
    save_figure(fig, "pdr_vs_delay_model_comparison", output_dir)


def main() -> None:  # pragma: no cover - CLI entry point
    args = parse_arguments()

    apply_ieee_style()
    if args.style:
        plt.style.use(args.style)

    metrics = load_metrics(args.results)

    plot_pdr_distribution_by_gateway(metrics)
    plot_downlink_delay_vs_gateways(metrics)
    plot_model_comparison(metrics)

    if args.show:
        plt.show()
    else:
        plt.close("all")


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
