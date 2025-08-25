"""Helpers for BER/SER calculations using analytical LoRa expressions."""

from __future__ import annotations

import math


def calculate_ber(snir: float, sf: int) -> float:
    r"""Return BER using Croce et al. (2018) approximation.

    The expression models the bit error probability of LoRa in AWGN as
    :math:`0.5\,\mathrm{erfc}\left(\sqrt{\mathrm{SNR}\,2^{SF}/(2\pi)}\right)`.
    ``snir`` is the linear signal-to-noise ratio.
    """

    n = 2 ** sf
    arg = math.sqrt(snir * n / (2.0 * math.pi))
    ber = 0.5 * math.erfc(arg)
    return min(max(ber, 0.0), 1.0)


def calculate_ser(snir: float, sf: int) -> float:
    """Return SER from BER for an ``sf``-bit LoRa symbol."""

    ber = calculate_ber(snir, sf)
    ser = 1.0 - (1.0 - ber) ** sf
    return min(max(ser, 0.0), 1.0)
