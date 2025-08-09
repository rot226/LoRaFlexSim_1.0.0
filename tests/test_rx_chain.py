from simulateur_lora_sfrd.launcher.simulator import Simulator
from simulateur_lora_sfrd.launcher.advanced_channel import AdvancedChannel
from simulateur_lora_sfrd.launcher.channel import Channel
import math
import pytest


def test_rx_chain_single_node():
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=3,
        mobility=False,
        seed=1,
    )
    sim.run()
    metrics = sim.get_metrics()
    assert metrics["PDR"] > 0
    assert metrics["pdr_by_node"][1] > 0


def test_rx_chain_multiple_nodes():
    sim = Simulator(
        num_nodes=3,
        num_gateways=1,
        transmission_mode="Periodic",
        packet_interval=1.0,
        packets_to_send=3,
        mobility=False,
        seed=1,
    )
    sim.run()
    metrics = sim.get_metrics()
    assert metrics["PDR"] > 0
    for pdr in metrics["pdr_by_node"].values():
        assert pdr > 0


def test_directional_antenna_gain():
    ch = AdvancedChannel()
    ch.base.shadowing_std = 0.0
    rssi1, _ = ch.compute_rssi(
        14.0,
        10.0,
        tx_pos=(0.0, 0.0, 0.0),
        rx_pos=(10.0, 0.0, 0.0),
        tx_angle=0.0,
        rx_angle=math.pi,
    )
    rssi2, _ = ch.compute_rssi(
        14.0,
        10.0,
        tx_pos=(0.0, 0.0, 0.0),
        rx_pos=(10.0, 0.0, 0.0),
        tx_angle=math.pi / 2,
        rx_angle=math.pi,
    )
    assert rssi2 < rssi1


def test_radio_state_energy():
    ch = Channel(
        phy_model="omnet",
        tx_current_a=1.0,
        rx_current_a=0.5,
        idle_current_a=0.1,
        voltage_v=1.0,
    )
    phy = ch.omnet_phy
    phy.start_tx()
    phy.update(1.0)
    phy.stop_tx()
    phy.update(1.0)
    phy.stop_rx()
    phy.update(1.0)
    assert phy.energy_tx == pytest.approx(1.0)
    assert phy.energy_rx == pytest.approx(0.5)
    assert phy.energy_idle == pytest.approx(0.1)
    assert phy.radio_state == "IDLE"
