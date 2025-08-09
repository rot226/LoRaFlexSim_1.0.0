from pathlib import Path
import pytest

from simulateur_lora_sfrd.launcher.channel import Channel
from simulateur_lora_sfrd.launcher.omnet_phy import OmnetPHY
from simulateur_lora_sfrd.launcher.compare_flora import load_flora_metrics


def test_omnet_phy_flora_capture_matches_sca():
    pytest.importorskip('pandas')
    ch = Channel(phy_model="omnet", flora_capture=True, shadowing_std=0.0, fast_fading_std=0.0)
    phy: OmnetPHY = ch.omnet_phy
    rssi_list = [-50.0, -55.0]
    start_list = [0.0, 0.0]
    end_list = [0.1, 0.1]
    sf_list = [7, 7]
    freq_list = [868e6, 868e6]
    winners = phy.capture(
        rssi_list,
        start_list=start_list,
        end_list=end_list,
        sf_list=sf_list,
        freq_list=freq_list,
    )
    collisions = len(rssi_list) - sum(1 for w in winners if w)
    sca = Path(__file__).parent / "data" / "flora_capture_expected.sca"
    flora = load_flora_metrics(sca)
    assert collisions == flora["collisions"]
