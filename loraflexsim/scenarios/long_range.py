"""Helper utilities to build deterministic long range scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..launcher import Channel, Simulator

# Target a 24 km x 24 km deployment area to accommodate 12 km links.
LONG_RANGE_AREA_SIZE: float = 24_000.0
LONG_RANGE_DISTANCES: List[float] = [
    11_000.0,
    10_800.0,
    10_000.0,
    9_000.0,
    8_000.0,
    7_000.0,
    6_000.0,
    5_000.0,
    4_000.0,
]
LONG_RANGE_SPREADING_FACTORS: List[int] = [12, 12, 12, 11, 11, 10, 10, 9, 9]
LONG_RANGE_BANDWIDTHS: tuple[int, int, int] = (125_000, 250_000, 500_000)


@dataclass(frozen=True)
class LongRangeParameters:
    """Hardware assumptions used to stabilise long range simulations."""

    tx_power_dBm: float
    tx_antenna_gain_dB: float
    rx_antenna_gain_dB: float
    cable_loss_dB: float
    packet_interval_s: float = 1200.0
    packets_per_node: int = 8
    shadowing_std_dB: float = 0.0
    distances: tuple[float, ...] | None = None
    spreading_factors: tuple[int, ...] | None = None
    area_size_m: float | None = None


LONG_RANGE_RECOMMENDATIONS: Dict[str, LongRangeParameters] = {
    "flora": LongRangeParameters(
        tx_power_dBm=23.0,
        tx_antenna_gain_dB=16.0,
        rx_antenna_gain_dB=16.0,
        cable_loss_dB=0.5,
    ),
    "flora_hata": LongRangeParameters(
        tx_power_dBm=23.0,
        tx_antenna_gain_dB=16.0,
        rx_antenna_gain_dB=16.0,
        cable_loss_dB=0.5,
    ),
    "rural_long_range": LongRangeParameters(
        tx_power_dBm=16.0,
        tx_antenna_gain_dB=6.0,
        rx_antenna_gain_dB=6.0,
        cable_loss_dB=0.5,
    ),
    "very_long_range": LongRangeParameters(
        tx_power_dBm=27.0,
        tx_antenna_gain_dB=19.0,
        rx_antenna_gain_dB=19.0,
        cable_loss_dB=0.5,
        distances=(
            15_000.0,
            13_500.0,
            12_000.0,
            10_800.0,
            10_000.0,
            9_000.0,
            8_000.0,
            7_000.0,
            6_000.0,
            5_000.0,
            4_000.0,
        ),
        spreading_factors=(12, 12, 12, 12, 11, 11, 10, 10, 9, 9, 9),
        area_size_m=32_000.0,
    ),
}


def _loss_model(preset: str) -> str:
    return "hata" if preset == "flora_hata" else "lognorm"


def _preset_distances(params: LongRangeParameters) -> tuple[float, ...]:
    return params.distances or tuple(LONG_RANGE_DISTANCES)


def _preset_spreading_factors(params: LongRangeParameters) -> tuple[int, ...]:
    return params.spreading_factors or tuple(LONG_RANGE_SPREADING_FACTORS)


def _preset_area_size(params: LongRangeParameters) -> float:
    return params.area_size_m or LONG_RANGE_AREA_SIZE


def create_long_range_channels(preset: str) -> List[Channel]:
    """Return channels tuned for large area validation."""

    if preset not in LONG_RANGE_RECOMMENDATIONS:
        raise ValueError(f"Unknown long range preset: {preset}")
    params = LONG_RANGE_RECOMMENDATIONS[preset]
    channels: List[Channel] = []
    for bandwidth in LONG_RANGE_BANDWIDTHS:
        channel = Channel(environment=preset, flora_loss_model=_loss_model(preset))
        channel.shadowing_std = params.shadowing_std_dB
        channel.bandwidth = bandwidth
        channel.tx_antenna_gain_dB = params.tx_antenna_gain_dB
        channel.rx_antenna_gain_dB = params.rx_antenna_gain_dB
        channel.cable_loss_dB = params.cable_loss_dB
        channels.append(channel)
    return channels


def configure_long_range_nodes(sim: Simulator, params: LongRangeParameters) -> None:
    """Deterministically place nodes on the x axis and assign SF/BW pairs."""

    distances = _preset_distances(params)
    spreading_factors = _preset_spreading_factors(params)
    if len(distances) != len(spreading_factors):
        raise ValueError("Distances and spreading factors must have matching lengths")
    if len(sim.nodes) != len(distances):
        raise ValueError(
            "Long range scenario expects exactly"
            f" {len(distances)} nodes"
        )
    gateway = sim.gateways[0]
    center_x = gateway.x
    center_y = gateway.y
    channels = sim.multichannel.channels
    for idx, node in enumerate(sim.nodes):
        node.x = center_x + distances[idx]
        node.y = center_y
        node.sf = spreading_factors[idx]
        node.tx_power = params.tx_power_dBm
        node.channel = channels[idx % len(channels)]
        node.chmask = 1 << (idx % len(channels))


def build_long_range_simulator(
    preset: str,
    *,
    seed: int = 2,
    packets_per_node: int | None = None,
) -> Simulator:
    """Create a :class:`Simulator` configured for the large area scenario."""

    if preset not in LONG_RANGE_RECOMMENDATIONS:
        raise ValueError(f"Unknown long range preset: {preset}")
    params = LONG_RANGE_RECOMMENDATIONS[preset]
    distances = _preset_distances(params)
    spreading_factors = _preset_spreading_factors(params)
    if len(distances) != len(spreading_factors):
        raise ValueError("Distances and spreading factors must have matching lengths")
    channels = create_long_range_channels(preset)
    simulator = Simulator(
        num_nodes=len(distances),
        num_gateways=1,
        area_size=_preset_area_size(params),
        transmission_mode="Periodic",
        packet_interval=params.packet_interval_s,
        packets_to_send=packets_per_node or params.packets_per_node,
        mobility=False,
        seed=seed,
        flora_mode=True,
        channels=channels,
    )
    configure_long_range_nodes(simulator, params)
    return simulator
