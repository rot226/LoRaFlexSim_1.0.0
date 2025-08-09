import pytest
from simulateur_lora_sfrd.launcher.channel import Channel


def test_startup_current_energy():
    ch = Channel(
        phy_model="omnet",
        tx_current_a=1.0,
        rx_current_a=0.5,
        idle_current_a=0.0,
        voltage_v=1.0,
    )
    phy = ch.omnet_phy
    phy.tx_start_delay_s = 1.0
    phy.rx_start_delay_s = 0.5
    phy.tx_start_current_a = 2.0
    phy.rx_start_current_a = 1.5
    phy.tx_state = "off"
    phy.rx_state = "off"

    phy.start_tx()
    phy.update(1.0)
    assert phy.energy_tx == pytest.approx(2.0)
    phy.update(1.0)
    assert phy.energy_tx == pytest.approx(3.0)
    phy.stop_tx()

    phy.start_rx()
    phy.update(0.5)
    assert phy.energy_rx == pytest.approx(0.75)
    phy.update(1.0)
    assert phy.energy_rx == pytest.approx(1.25)
    phy.stop_rx()
    phy.update(1.0)

    assert phy.radio_state == "IDLE"

