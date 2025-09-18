import pytest

from loraflexsim.launcher.lorawan import DutyCycleReq, LoRaWANFrame
from loraflexsim.launcher.simulator import Simulator


@pytest.mark.xfail(reason="Le DutyCycleReq ne pilote pas encore le DutyCycleManager", strict=True)
def test_duty_cycle_command_updates_manager():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=0,
        mobility=False,
        duty_cycle=1.0,
        seed=0,
    )
    node = sim.nodes[0]
    frame = LoRaWANFrame(
        mhdr=0x60,
        fctrl=0,
        fcnt=0,
        payload=DutyCycleReq(max_duty_cycle=4).to_bytes(),
        confirmed=False,
    )
    node.handle_downlink(frame)
    assert sim.duty_cycle_manager is not None
    expected_duty_cycle = 1 / (2 ** 4)
    assert sim.duty_cycle_manager.duty_cycle == pytest.approx(expected_duty_cycle)
