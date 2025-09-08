"""Utilities for configuring Matplotlib plots with consistent style."""
from __future__ import annotations

import os
from typing import Optional

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - matplotlib optional at runtime
    plt = None  # type: ignore


def configure_style(style: Optional[str] = None) -> None:
    """Configure Matplotlib default style for high quality figures.

    Parameters
    ----------
    style:
        Optional style name or path passed to :func:`matplotlib.pyplot.style.use`.
        If ``None``, the value of the ``MPLSTYLE`` environment variable is used.
        When both are missing, the Matplotlib default style is kept.

    The function sets a serif font family and a default DPI of 300 for both on
    screen and saved figures.  It also configures ``pdf`` and ``ps`` font types
    to 42 to ensure vectorised text in outputs.
    """
    if plt is None:  # pragma: no cover - plotting not available
        return

    style_name = style or os.getenv("MPLSTYLE")
    if style_name and hasattr(plt, "style"):
        try:
            plt.style.use(style_name)
        except OSError:
            # Unknown style path/name; fall back to default silently
            pass

    if hasattr(plt, "rcParams"):
        plt.rcParams.update(
            {
                "font.family": "serif",
                "figure.dpi": 300,
                "savefig.dpi": 300,
                "pdf.fonttype": 42,
                "ps.fonttype": 42,
            }
        )

