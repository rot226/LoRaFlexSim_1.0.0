import pytest

try:  # pragma: no cover - exercised via skip when NumPy missing
    import numpy as np
except Exception:  # pragma: no cover - numpy optional in test env
    np = None
from loraflexsim.launcher.channel import Channel
from loraflexsim.run import simulate, PAYLOAD_SIZE
from traffic.rng_manager import RngManager
from traffic.exponential import sample_interval


def test_simulate_single_node_periodic():
    rng_manager = RngManager(0)
    delivered, collisions, pdr, energy, avg_delay, throughput = simulate(
        1,
        1,
        "Periodic",
        1.0,
        10,
        rng_manager=rng_manager,
    )
    assert delivered == 10
    assert collisions == 0
    assert pdr == 100.0
    sf_rng = RngManager(0).get_stream("sf", 0)
    sf_value = 7 + sf_rng.integers(0, 6)
    channel = Channel(
        tx_current_a=0.06,
        rx_current_a=0.011,
        idle_current_a=1e-6,
        voltage_v=3.3,
    )
    airtime = channel.airtime(sf_value, payload_size=PAYLOAD_SIZE)
    per_tx_energy = ((0.06 - 1e-6) + (0.011 - 1e-6)) * 3.3 * airtime
    idle_energy = (1 + 1) * 1e-6 * 3.3 * 10
    expected_energy = per_tx_energy * delivered + idle_energy
    assert pytest.approx(energy, rel=1e-6) == expected_energy
    assert avg_delay == 0
    assert throughput == PAYLOAD_SIZE * 8 * delivered / 10


def test_simulate_periodic_float_interval():
    rng_manager = RngManager(0)
    delivered, collisions, pdr, _, _, _ = simulate(
        1,
        1,
        "Periodic",
        2.5,
        10,
        rng_manager=rng_manager,
    )
    assert delivered == 4
    assert collisions == 0
    assert pdr == 100.0


@pytest.mark.parametrize(
    "nodes, gateways, mode, interval, steps",
    [
        (0, 1, "random", 10.0, 10),
        (1, 0, "random", 10.0, 10),
        (1, 1, "random", 0.0, 10),
        (1, 1, "random", 10.0, 0),
        (1, 1, "bad", 10.0, 10),
    ],
)
def test_simulate_invalid_parameters(nodes, gateways, mode, interval, steps):
    with pytest.raises(ValueError):
        simulate(nodes, gateways, mode, interval, steps, rng_manager=RngManager(0))


@pytest.mark.parametrize(
    "param,value",
    [
        ("nodes", 1.5),
        ("nodes", True),
        ("gateways", 2.2),
        ("gateways", False),
        ("channels", 3.3),
        ("channels", True),
        ("steps", 4.4),
        ("steps", True),
    ],
)
def test_simulate_rejects_non_integer_counts(param, value):
    kwargs = dict(
        nodes=1, gateways=1, mode="Random", interval=10.0, steps=10, channels=1
    )
    kwargs[param] = value
    with pytest.raises(TypeError):
        simulate(rng_manager=RngManager(0), **kwargs)


@pytest.mark.skipif(np is None or not hasattr(np, "int32"), reason="NumPy required")
def test_simulate_accepts_numpy_integer_types():
    rng_manager = RngManager(0)
    delivered, collisions, pdr, energy, avg_delay, throughput = simulate(
        np.int32(1),
        np.int64(1),
        "Periodic",
        1.0,
        np.int16(10),
        channels=np.int8(1),
        rng_manager=rng_manager,
    )
    assert delivered == 10
    assert collisions == 0
    assert pdr == 100.0
    assert pytest.approx(energy, rel=1e-6) == 0.132619833984
    assert avg_delay == 0
    assert throughput == PAYLOAD_SIZE * 8 * delivered / 10


def test_simulate_random_no_rescale():
    rng_manager = RngManager(0)
    delivered, collisions, _, _, _, _ = simulate(
        1,
        1,
        "Random",
        10.0,
        100,
        rng_manager=rng_manager,
    )

    rng = RngManager(0).get_stream("traffic", 0)
    expected = []
    t = sample_interval(10.0, rng)
    while t < 100:
        expected.append(t)
        t += sample_interval(10.0, rng)

    assert collisions == 0
    assert delivered == len(expected)


def test_pdr_decreases_with_overlap():
    base_params = dict(nodes=6, gateways=1, mode="Random", interval=20.0, steps=500)

    delivered_low, collisions_low, pdr_low, *_ = simulate(
        channels=3,
        rng_manager=RngManager(42),
        **base_params,
    )
    delivered_high, collisions_high, pdr_high, *_ = simulate(
        channels=1,
        rng_manager=RngManager(42),
        **base_params,
    )

    assert delivered_low >= delivered_high
    assert collisions_high > collisions_low
    assert pdr_high < pdr_low
