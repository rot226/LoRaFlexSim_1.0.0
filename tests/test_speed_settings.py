import math

import pytest

from loraflexsim.run import apply_speed_settings


def test_fast_mode_halves_nodes_and_limits_steps():
    nodes, steps = apply_speed_settings(200, 10_000, fast=True)
    assert nodes == 100
    expected_steps = min(10_000, max(600, math.ceil(10_000 * 0.1)))
    assert steps == expected_steps


def test_sample_size_fraction():
    nodes, steps = apply_speed_settings(50, 1_000, sample_size=0.25)
    assert nodes == 50
    assert steps == 250


def test_invalid_sample_size_raises():
    with pytest.raises(ValueError):
        apply_speed_settings(10, 100, sample_size=1.5)


def test_invalid_nodes_raise():
    with pytest.raises(ValueError):
        apply_speed_settings(0, 100)
