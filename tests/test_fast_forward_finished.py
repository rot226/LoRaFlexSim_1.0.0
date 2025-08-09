import pytest

from simulateur_lora_sfrd.launcher.simulator import Simulator
pn = pytest.importorskip("panel")
import simulateur_lora_sfrd.launcher.dashboard as dashboard  # noqa: E402


def test_fast_forward_on_finished_simulation():
    sim = Simulator(num_nodes=1, num_gateways=1, packets_to_send=1, mobility=False)
    sim.run()
    assert not sim.event_queue

    dashboard.sim = sim
    dashboard.fast_forward_button.disabled = False
    dashboard.fast_forward_progress.value = 0
    dashboard.fast_forward_progress.visible = False

    dashboard.fast_forward()

    assert dashboard.fast_forward_button.disabled
    assert dashboard.fast_forward_progress.value == 0
    assert dashboard.fast_forward_progress.visible is False
    assert dashboard.sim.running is False
