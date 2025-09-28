import configparser
from os import PathLike

import pytest

from loraflexsim.launcher import adr_standard_1
from loraflexsim.launcher.advanced_channel import AdvancedChannel
from loraflexsim.launcher.channel import Channel
from loraflexsim.launcher.gateway import FLORA_NON_ORTH_DELTA
from loraflexsim.launcher.simulator import Simulator


def test_advanced_degradation_uses_advanced_capture_and_thresholds():
    base_channel = Channel(bandwidth=125_000, sensitivity_margin_dB=2.5)
    sim = Simulator(num_nodes=1, packets_to_send=0, channels=[base_channel])

    adr_standard_1.apply(
        sim,
        degrade_channel=True,
        profile="flora",
        capture_mode="advanced",
    )

    assert sim.multichannel.channels, "La dégradation doit produire au moins un canal."
    for channel in sim.multichannel.channels:
        assert isinstance(channel, AdvancedChannel)
        assert channel.advanced_capture is True
        assert channel.flora_capture is False
        expected_threshold = Channel.flora_detection_threshold(12, channel.bandwidth)
        expected_threshold += channel.sensitivity_margin_dB
        assert channel.detection_threshold(12) == expected_threshold

    assert sim.channel is sim.multichannel.channels[0]
    assert sim.channel.orthogonal_sf is False
    assert sim.channel.non_orth_delta == FLORA_NON_ORTH_DELTA
    assert sim.network_server.channel is sim.channel
    assert sim.network_server.channel.orthogonal_sf is False
    assert sim.network_server.channel.non_orth_delta == FLORA_NON_ORTH_DELTA


def test_advanced_degradation_reads_channel_overrides(monkeypatch):
    base_channel = Channel(bandwidth=125_000)
    sim = Simulator(num_nodes=1, packets_to_send=0, channels=[base_channel])

    fake_config = """[channel]
    fading=none
    rician_k=4.2
    """

    original_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        if isinstance(filenames, (str, PathLike)):
            path = str(filenames)
            if path.endswith("config.ini"):
                self.read_string(fake_config)
                return [path]
            return original_read(self, filenames, encoding=encoding)
        if isinstance(filenames, (list, tuple)):
            read_files: list[str] = []
            for entry in filenames:
                read_files.extend(fake_read(self, entry, encoding=encoding))
            return read_files
        return original_read(self, filenames, encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", fake_read)

    adr_standard_1.apply(
        sim,
        degrade_channel=True,
        profile="flora",
        capture_mode="advanced",
    )

    for channel in sim.multichannel.channels:
        assert isinstance(channel, AdvancedChannel)
        assert channel.fading is None
        assert channel.rician_k == pytest.approx(4.2)
