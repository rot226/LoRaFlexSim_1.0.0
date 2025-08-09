from traffic.rng_manager import RngManager


def test_rng_seed_determinism():
    mgr1 = RngManager(123)
    mgr2 = RngManager(123)
    rng1 = mgr1.get_stream("traffic", 1)
    rng2 = mgr2.get_stream("traffic", 1)
    assert rng1.random() == rng2.random()
