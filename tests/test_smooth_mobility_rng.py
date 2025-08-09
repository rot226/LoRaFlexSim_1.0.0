from simulateur_lora_sfrd.launcher.smooth_mobility import SmoothMobility
from simulateur_lora_sfrd.launcher.node import Node
from traffic.rng_manager import RngManager


def test_smooth_mobility_determinism():
    mgr1 = RngManager(42)
    mob1 = SmoothMobility(100.0, rng=mgr1.get_stream("mob", 0))
    node1 = Node(1, 0.0, 0.0, 7, 14)
    mob1.assign(node1)
    path1 = node1.path

    mgr2 = RngManager(42)
    mob2 = SmoothMobility(100.0, rng=mgr2.get_stream("mob", 0))
    node2 = Node(1, 0.0, 0.0, 7, 14)
    mob2.assign(node2)
    path2 = node2.path

    assert path1 == path2
