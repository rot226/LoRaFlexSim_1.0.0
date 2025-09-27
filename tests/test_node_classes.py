import math
from types import SimpleNamespace

from loraflexsim.launcher.energy_profiles import EnergyProfile
from loraflexsim.launcher.node import Node
from loraflexsim.launcher.lorawan import DeviceModeInd, DeviceModeConf


def make_node(class_type: str) -> Node:
    profile = EnergyProfile(startup_time_s=0.0)
    return Node(
        node_id=1,
        x=0.0,
        y=0.0,
        sf=7,
        tx_power=14.0,
        class_type=class_type,
        energy_profile=profile,
    )


def test_class_c_starts_in_rx():
    node = make_node("C")
    assert node.state == "rx"


def test_class_b_defaults_to_sleep():
    node = make_node("B")
    assert node.state == "sleep"


def test_distance_to_supports_altitude():
    node = make_node("A")
    other = make_node("A")
    other.x = 3.0
    other.y = 4.0
    other.altitude = 12.0
    node.altitude = 8.0
    assert math.isclose(node.distance_to(other), math.sqrt(41))


def test_device_mode_ind_energy_accounting_and_state_update():
    profile = EnergyProfile(
        voltage_v=3.0,
        sleep_current_a=0.1,
        rx_current_a=0.2,
        startup_time_s=0.0,
    )
    node = Node(
        node_id=42,
        x=0.0,
        y=0.0,
        sf=7,
        tx_power=14.0,
        class_type="A",
        energy_profile=profile,
    )
    node.last_state_time = 0.0
    node.state = "sleep"

    class SimulatorStub:
        def __init__(self, current_time: float):
            self.current_time = current_time
            self.calls: list[tuple[Node, float]] = []

        def ensure_class_c_rx_window(self, node: Node, time: float) -> None:
            self.calls.append((node, time))

    simulator = SimulatorStub(10.0)
    node.simulator = simulator

    frame = SimpleNamespace(
        fcnt=0,
        fctrl=0,
        confirmed=False,
        payload=DeviceModeInd("C").to_bytes(),
    )

    node.handle_downlink(frame)

    expected_energy = profile.sleep_current_a * profile.voltage_v * simulator.current_time
    assert math.isclose(node.energy_sleep, expected_energy)
    assert math.isclose(node.energy_consumed, expected_energy)
    assert node.last_state_time == simulator.current_time
    assert node.state == "rx"
    assert node.pending_mac_cmd == DeviceModeConf("C").to_bytes()
    assert simulator.calls and simulator.calls[0][0] is node
    assert simulator.calls[0][1] == simulator.current_time
