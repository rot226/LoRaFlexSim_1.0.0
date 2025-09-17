"""Integration tests validating LoRaFlexSim against FLoRa baselines."""

from __future__ import annotations

from pathlib import Path

import pytest

try:  # pragma: no cover - optional dependency
    import pandas as _pd  # noqa: F401
except Exception:  # pragma: no cover - skip if pandas unusable
    pytest.skip("pandas is required for validation comparisons", allow_module_level=True)

from loraflexsim.validation import (
    SCENARIOS,
    compare_to_reference,
    load_flora_reference,
    run_validation,
)

pytestmark = pytest.mark.slow


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda sc: sc.name)
def test_scenario_matches_flora_reference(scenario):
    """Each validation scenario stays within the tolerance bound."""

    assert Path(scenario.flora_config).exists(), f"Missing FLoRa config {scenario.flora_config}"
    assert Path(scenario.flora_reference).exists(), f"Missing reference file {scenario.flora_reference}"

    sim = scenario.build_simulator()
    metrics = run_validation(sim, scenario.run_steps)
    reference = load_flora_reference(scenario.flora_reference)
    deltas = compare_to_reference(metrics, reference, scenario.tolerances)

    assert deltas["PDR"] <= scenario.tolerances.pdr, (
        f"PDR delta {deltas['PDR']:.3f} exceeds tolerance {scenario.tolerances.pdr:.3f}"
    )
    assert deltas["collisions"] <= scenario.tolerances.collisions, (
        f"Collision delta {deltas['collisions']:.3f} exceeds tolerance {scenario.tolerances.collisions:.3f}"
    )
    assert deltas["snr"] <= scenario.tolerances.snr, (
        f"SNR delta {deltas['snr']:.3f} exceeds tolerance {scenario.tolerances.snr:.3f}"
    )
