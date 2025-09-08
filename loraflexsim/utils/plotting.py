"""Plotting utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence


def save_multi_format(
    fig,
    base_path: str | Path,
    formats: Sequence[str] | None = ("png", "jpg", "eps"),
    dpi: int = 300,
):
    """Save a Matplotlib figure to multiple formats.

    Parameters
    ----------
    fig:
        Matplotlib figure instance.
    base_path:
        Path without extension where figures should be written.
    formats:
        Iterable of extensions (without leading dots). Defaults to
        ``("png", "jpg", "eps")``.
    dpi:
        Dots per inch for raster formats (png, jpg). Ignored for vector
        formats.
    """
    base = Path(base_path)
    base.parent.mkdir(parents=True, exist_ok=True)
    saved = []
    for ext in formats or []:
        ext = ext.lstrip(".")
        path = base.with_suffix(f".{ext}")
        dpi_val = dpi if ext.lower() in {"png", "jpg", "jpeg"} else None
        fig.savefig(path, dpi=dpi_val)
        saved.append(path)
    return saved


def parse_formats(value: str) -> list[str]:
    """Parse a comma-separated list of formats."""
    return [fmt.strip() for fmt in value.split(",") if fmt.strip()]


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI helper
    import argparse
    import matplotlib.pyplot as plt

    parser = argparse.ArgumentParser(description="Save a blank figure to multiple formats")
    parser.add_argument("output", help="Base path for output figure")
    parser.add_argument(
        "--formats",
        default="png,jpg,eps",
        help="Comma-separated list of formats",
    )
    args = parser.parse_args(argv)

    fig = plt.figure()
    save_multi_format(fig, args.output, parse_formats(args.formats))


if __name__ == "__main__":  # pragma: no cover
    main()
