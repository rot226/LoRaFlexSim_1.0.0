"""Tests unitaires des commandes MAC LoRaWAN pour ``Node.handle_downlink``."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from loraflexsim.launcher.energy_profiles import EnergyProfile
from loraflexsim.launcher.lorawan import (
    BeaconFreqAns,
    BeaconFreqReq,
    BeaconTimingAns,
    BeaconTimingReq,
    DevStatusAns,
    DevStatusReq,
    DeviceTimeAns,
    DeviceTimeReq,
    FragSessionDeleteAns,
    FragSessionDeleteReq,
    FragSessionSetupAns,
    FragSessionSetupReq,
    FragStatusAns,
    FragStatusReq,
    LinkCheckAns,
    LinkCheckReq,
    LoRaWANFrame,
    PingSlotChannelAns,
    PingSlotChannelReq,
    PingSlotInfoAns,
    PingSlotInfoReq,
    RXParamSetupAns,
    RXParamSetupReq,
    TxParamSetupReq,
)
from loraflexsim.launcher.node import Node


@dataclass
class SimulatorStub:
    """Stub minimal fournissant l'API utilisée par ``Node``."""

    current_time: float = 0.0

    def __post_init__(self) -> None:
        self.class_c_calls: list[tuple[Node, float]] = []

    def ensure_class_c_rx_window(self, node: Node, time: float) -> None:  # pragma: no cover - simple enregistrement
        self.class_c_calls.append((node, time))


@pytest.fixture
def node() -> Node:
    """Retourne un nœud avec un profil énergétique sans temporisation."""

    profile = EnergyProfile(
        startup_time_s=0.0,
        preamble_time_s=0.0,
        ramp_up_s=0.0,
        ramp_down_s=0.0,
        rx_window_duration=0.0,
    )
    test_node = Node(
        node_id=1,
        x=0.0,
        y=0.0,
        sf=7,
        tx_power=14.0,
        energy_profile=profile,
    )
    test_node.simulator = SimulatorStub()
    return test_node


def make_frame(payload: bytes) -> LoRaWANFrame:
    """Crée un cadre LoRaWAN minimal pour les tests."""

    return LoRaWANFrame(mhdr=0, fctrl=0, fcnt=0, payload=payload)


def test_link_check_request(node: Node) -> None:
    frame = make_frame(LinkCheckReq().to_bytes())
    node.handle_downlink(frame)
    assert node.pending_mac_cmd == LinkCheckAns(margin=255, gw_cnt=1).to_bytes()


def test_device_time_request(node: Node) -> None:
    node.fcnt_up = 42
    frame = make_frame(DeviceTimeReq().to_bytes())
    node.handle_downlink(frame)
    assert node.pending_mac_cmd == DeviceTimeAns(42).to_bytes()


def test_rx_param_setup(node: Node) -> None:
    req = RXParamSetupReq(rx1_dr_offset=2, rx2_datarate=5, frequency=869525000)
    frame = make_frame(req.to_bytes())
    node.handle_downlink(frame)
    assert node.rx1_dr_offset == 2
    assert node.rx2_datarate == 5
    assert node.rx2_frequency == 869525000
    assert node.pending_mac_cmd == RXParamSetupAns().to_bytes()


def test_tx_param_setup(node: Node) -> None:
    req = TxParamSetupReq(eirp=9, dwell_time=1)
    frame = make_frame(req.to_bytes())
    node.handle_downlink(frame)
    assert node.eirp == 9
    assert node.dwell_time == 1


def test_dev_status_request(node: Node) -> None:
    node.last_snr = 7.8
    frame = make_frame(DevStatusReq().to_bytes())
    node.handle_downlink(frame)
    expected = DevStatusAns(battery=255, margin=7).to_bytes()
    assert node.pending_mac_cmd == expected


def test_ping_slot_info_request(node: Node) -> None:
    req = PingSlotInfoReq(periodicity=3)
    frame = make_frame(req.to_bytes())
    node.handle_downlink(frame)
    assert node.ping_slot_periodicity == 3
    assert node.pending_mac_cmd == PingSlotInfoAns().to_bytes()


def test_ping_slot_channel_request(node: Node) -> None:
    req = PingSlotChannelReq(frequency=869525000, dr=5)
    frame = make_frame(req.to_bytes())
    node.handle_downlink(frame)
    assert node.ping_slot_frequency == 869525000
    assert node.ping_slot_dr == 5
    assert node.pending_mac_cmd == PingSlotChannelAns().to_bytes()


def test_beacon_frequency_request(node: Node) -> None:
    req = BeaconFreqReq(frequency=868300000)
    frame = make_frame(req.to_bytes())
    node.handle_downlink(frame)
    assert node.beacon_frequency == 868300000
    assert node.pending_mac_cmd == BeaconFreqAns().to_bytes()


def test_beacon_timing_answer(node: Node) -> None:
    ans = BeaconTimingAns(delay=512, channel=3)
    frame = make_frame(ans.to_bytes())
    node.handle_downlink(frame)
    assert node.beacon_delay == 512
    assert node.beacon_channel == 3
    assert node.pending_mac_cmd == BeaconTimingAns(0, 0).to_bytes()


def test_fragmentation_command_sequence(node: Node) -> None:
    setup = FragSessionSetupReq(index=1, nb_frag=10, frag_size=32)
    node.handle_downlink(make_frame(setup.to_bytes()))
    assert node.frag_sessions[1] == {"nb": 10, "size": 32}
    assert node.pending_mac_cmd == FragSessionSetupAns(1).to_bytes()

    status = FragStatusReq(index=1)
    node.handle_downlink(make_frame(status.to_bytes()))
    assert node.frag_sessions[1] == {"nb": 10, "size": 32}
    assert node.pending_mac_cmd == FragStatusAns(1, 0).to_bytes()

    delete = FragSessionDeleteReq(index=1)
    node.handle_downlink(make_frame(delete.to_bytes()))
    assert 1 not in node.frag_sessions
    assert node.pending_mac_cmd == FragSessionDeleteAns().to_bytes()


def test_fragmentation_delete_unknown_session(node: Node) -> None:
    delete = FragSessionDeleteReq(index=5)
    node.handle_downlink(make_frame(delete.to_bytes()))
    assert node.pending_mac_cmd == FragSessionDeleteAns().to_bytes()
    assert node.frag_sessions == {}


def test_beacon_timing_request_without_answer(node: Node) -> None:
    req = BeaconTimingReq()
    frame = make_frame(req.to_bytes())
    node.handle_downlink(frame)
    assert node.beacon_delay is None
    assert node.beacon_channel is None
    assert node.pending_mac_cmd == BeaconTimingAns(0, 0).to_bytes()


def test_simulator_stub_keeps_class_c_calls(node: Node) -> None:
    node.handle_downlink(make_frame(PingSlotInfoReq(periodicity=1).to_bytes()))
    assert node.simulator.class_c_calls == []
