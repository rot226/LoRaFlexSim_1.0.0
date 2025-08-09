"""Helpers for OMNeT++-style BER/SER calculations."""

from __future__ import annotations

import math


def calculate_ber(snir: float, bandwidth: float, bitrate: float) -> float:
    """Return BER using the formula from LoRaModulation::calculateBER."""
    dsnr = 20.0 * snir * bandwidth / bitrate
    dsumk = 0.0
    for k in range(2, 8, 2):
        comb = math.comb(16, k)
        dsumk += comb * (
            math.exp(dsnr * (1.0 / k - 1.0))
            + math.exp(dsnr * (1.0 / (16 - k) - 1.0))
        )
    k = 8
    dsumk += math.comb(16, k) * math.exp(dsnr * (1.0 / k - 1.0))
    for k in range(3, 8, 2):
        comb = math.comb(16, k)
        dsumk -= comb * (
            math.exp(dsnr * (1.0 / k - 1.0))
            + math.exp(dsnr * (1.0 / (16 - k) - 1.0))
        )
    dsumk -= math.comb(16, 15) * math.exp(dsnr * (1.0 / 15 - 1.0))
    dsumk += math.comb(16, 16) * math.exp(dsnr * (1.0 / 16 - 1.0))
    return (8.0 / 15.0) * (1.0 / 16.0) * dsumk


def calculate_ser(snir: float, bandwidth: float, bitrate: float) -> float:
    """Return SER using a simple BER-to-SER approximation."""
    ber = calculate_ber(snir, bandwidth, bitrate)
    ser = 1.0 - (1.0 - ber) ** 4
    return min(max(ser, 0.0), 1.0)
