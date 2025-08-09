from simulateur_lora_sfrd.launcher.simulator import Simulator


def test_default_intervals_flora_mode():
    sim = Simulator(flora_mode=True)
    assert sim.packet_interval == 1000.0
    assert sim.first_packet_interval == 1000.0
    assert sim.detection_threshold_dBm == -110.0
    assert sim.min_interference_time == 5.0
    assert sim.channel.environment == "flora"
    assert sim.channel.multipath_taps == 3
