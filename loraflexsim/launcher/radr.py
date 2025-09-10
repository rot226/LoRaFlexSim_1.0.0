from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from .simulator import Simulator


@dataclass
class RADRModel:
    """Minimal reinforcement learning model for RADR.

    The model maintains a simple table of cumulative rewards for
    state-action pairs.  It is intentionally lightweight and serves as a
    placeholder for a more advanced learning algorithm.
    """

    q_table: Dict[Tuple[Tuple, str], float] = field(default_factory=dict)

    def update(self, state: Tuple, action: str, reward: float) -> None:
        """Update the cumulative reward for a given state and action."""
        key = (state, action)
        self.q_table[key] = self.q_table.get(key, 0.0) + reward

    def best_action(self, state: Tuple) -> str:
        """Return the best known action for *state* (placeholder)."""
        candidates = {a: r for (s, a), r in self.q_table.items() if s == state}
        if not candidates:
            return "default"
        return max(candidates, key=candidates.get)


def apply(sim: Simulator) -> None:
    """Configure the RADR ADR method using reinforcement learning."""
    sim.network_server.adr_method = "radr"
    sim.network_server.adr_model = RADRModel()

    def reward_callback(state: Tuple, action: str, success: bool) -> None:
        """Simple reward handler updating the RADR model.

        Parameters
        ----------
        state: Tuple
            Representation of the current environment state.
        action: str
            Action chosen by the ADR algorithm.
        success: bool
            Whether the transmission was successful.
        """
        reward = 1.0 if success else -1.0
        sim.network_server.adr_model.update(state, action, reward)

    sim.network_server.adr_reward = reward_callback
