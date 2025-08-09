from simulateur_lora_sfrd.launcher.simulator import Simulator
from simulateur_lora_sfrd.launcher.adr_standard_1 import apply as apply_adr
from simulateur_lora_sfrd.launcher.channel import Channel
from simulateur_lora_sfrd.launcher.multichannel import MultiChannel


def test_interval_with_degraded_channel():
    mean_interval = 2.0
    packets = 1000
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Random",
        packet_interval=mean_interval,
        packets_to_send=packets,
        pure_poisson_mode=True,
        mobility=False,
        seed=1,
    )
    apply_adr(sim, degrade_channel=True)
    sim.run()
    node = sim.nodes[0]
    average = node._last_arrival_time / node.packets_sent
    assert node.packets_sent == packets
    assert abs(average - mean_interval) / mean_interval < 0.02


def test_channels_identical_after_degrade():
    channels = [
        Channel(frequency_hz=868.1e6),
        Channel(frequency_hz=868.3e6),
        Channel(frequency_hz=868.5e6),
    ]
    multi = MultiChannel(channels)
    sim = Simulator(
        num_nodes=1,
        num_gateways=1,
        transmission_mode="Random",
        packet_interval=1.0,
        packets_to_send=1,
        pure_poisson_mode=True,
        mobility=False,
        channels=multi,
        seed=1,
    )
    apply_adr(sim, degrade_channel=True)

    attrs = [
        "path_loss_exp",
        "shadowing_std",
        "detection_threshold_dBm",
        "capture_threshold_dB",
    ]
    reference = sim.multichannel.channels[0]
    for ch in sim.multichannel.channels[1:]:
        for attr in attrs:
            assert getattr(ch, attr) == getattr(reference, attr)
