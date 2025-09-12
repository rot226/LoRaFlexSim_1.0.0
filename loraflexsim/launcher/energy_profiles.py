from dataclasses import dataclass
from collections import defaultdict

DEFAULT_TX_CURRENT_MAP_A: dict[float, float] = {
    2.0: 0.02,  # ~20 mA
    5.0: 0.027,  # ~27 mA
    8.0: 0.035,  # ~35 mA
    11.0: 0.045,  # ~45 mA
    14.0: 0.060,  # ~60 mA
    17.0: 0.10,  # ~100 mA
    20.0: 0.12,  # ~120 mA
}

@dataclass(frozen=True)
class EnergyProfile:
    """Energy consumption parameters for a LoRa node."""

    voltage_v: float = 3.3
    sleep_current_a: float = 1e-6
    rx_current_a: float = 11e-3
    listen_current_a: float = 0.0
    process_current_a: float = 0.0
    # Additional radio state modelling parameters
    startup_current_a: float = 0.0
    startup_time_s: float = 0.0
    preamble_current_a: float = 0.0
    preamble_time_s: float = 0.0
    ramp_up_s: float = 0.0
    ramp_down_s: float = 0.0
    rx_window_duration: float = 0.0
    tx_current_map_a: dict[float, float] | None = None

    def get_tx_current(self, power_dBm: float) -> float:
        """Return TX current for the closest power value in the mapping."""
        if not self.tx_current_map_a:
            return 0.0
        key = min(self.tx_current_map_a.keys(), key=lambda k: abs(k - power_dBm))
        return self.tx_current_map_a[key]

    def energy_for(
        self, state: str, duration_s: float, power_dBm: float | None = None
    ) -> float:
        """Return the energy (J) spent in ``state`` during ``duration_s`` seconds."""
        if duration_s <= 0:
            return 0.0
        if state == "sleep":
            current = self.sleep_current_a
        elif state == "rx":
            current = self.rx_current_a
        elif state == "listen":
            current = self.listen_current_a
        elif state == "processing":
            current = self.process_current_a
        elif state == "tx":
            if power_dBm is None:
                raise ValueError("power_dBm is required for TX energy computation")
            current = self.get_tx_current(power_dBm)
        else:
            current = 0.0
        return current * self.voltage_v * duration_s


class EnergyAccumulator:
    """Simple accumulator tracking energy per state."""

    def __init__(self) -> None:
        self._by_state: defaultdict[str, float] = defaultdict(float)

    def add(self, state: str, energy_joules: float) -> None:
        self._by_state[state] += energy_joules

    def get(self, state: str) -> float:
        return self._by_state.get(state, 0.0)

    def total(self) -> float:
        return sum(self._by_state.values())

    def to_dict(self) -> dict[str, float]:
        return dict(self._by_state)


# Default profile based on the FLoRa model (OMNeT++)
FLORA_PROFILE = EnergyProfile(
    tx_current_map_a=DEFAULT_TX_CURRENT_MAP_A,
    startup_current_a=1.6e-3,
    startup_time_s=1e-3,
    preamble_current_a=5e-3,
    preamble_time_s=1e-3,
    ramp_up_s=1e-3,
    ramp_down_s=1e-3,
)

# Example of a lower power transceiver profile
LOW_POWER_TX_MAP_A: dict[float, float] = {
    2.0: 0.015,
    5.0: 0.022,
    8.0: 0.029,
    11.0: 0.040,
    14.0: 0.055,
}

LOW_POWER_PROFILE = EnergyProfile(rx_current_a=7e-3, tx_current_map_a=LOW_POWER_TX_MAP_A)

# ------------------------------------------------------------------
# Profile registry helpers
# ------------------------------------------------------------------

PROFILES: dict[str, EnergyProfile] = {
    "flora": FLORA_PROFILE,
    "low_power": LOW_POWER_PROFILE,
}


def register_profile(name: str, profile: EnergyProfile) -> None:
    """Register a named energy profile."""
    PROFILES[name.lower()] = profile


def get_profile(name: str) -> EnergyProfile:
    """Retrieve a named energy profile."""
    key = name.lower()
    if key not in PROFILES:
        raise KeyError(f"Unknown energy profile: {name}")
    return PROFILES[key]
