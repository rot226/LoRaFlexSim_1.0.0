"""Regression test for the FLoRa log-normal shadowing model."""

import math

import pytest

from loraflexsim.launcher.channel import Channel


@pytest.mark.parametrize(
    "distance",
    [
        40.0,
        80.0,
        200.0,
        1000.0,
        5000.0,
    ],
)
def test_flora_path_loss_matches_flora_reference(distance: float) -> None:
    """Ensure Channel reproduces FLoRa's LoRaLogNormalShadowing curve."""

    channel = Channel(environment="flora", phy_model="flora")
    loss = channel.path_loss(distance)

    gamma = 2.08
    d0 = 40.0
    pl_d0 = 127.41
    expected = pl_d0 + 10 * gamma * math.log10(distance / d0)

    assert loss == pytest.approx(expected, rel=1e-12, abs=1e-9)
