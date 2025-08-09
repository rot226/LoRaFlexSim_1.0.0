import math
from simulateur_lora_sfrd.launcher.downlink_scheduler import DownlinkScheduler
from simulateur_lora_sfrd.launcher.gateway import Gateway
from simulateur_lora_sfrd.launcher.node import Node


def test_schedule_beacon_time():
    scheduler = DownlinkScheduler()
    gw = Gateway(1, 0, 0)
    t = scheduler.schedule_beacon(62.0, b"x", gw, beacon_interval=10.0)
    assert math.isclose(t, 70.0)
    frame, gw2 = scheduler.pop_ready(0, 70.0)
    assert frame == b"x" and gw2 is gw


def test_schedule_class_b():
    scheduler = DownlinkScheduler()
    gw = Gateway(1, 0, 0)
    node = Node(1, 0.0, 0.0, 7, 14, class_type="B")
    t = scheduler.schedule_class_b(
        node,
        0.0,
        b"a",
        gw,
        beacon_interval=128.0,
        ping_slot_interval=1.0,
        ping_slot_offset=2.0,
    )
    assert math.isclose(t, 2.0)
    frame, gw2 = scheduler.pop_ready(node.id, t)
    assert frame == b"a" and gw2 is gw


def test_schedule_class_c_delay():
    scheduler = DownlinkScheduler(link_delay=0.5)
    gw = Gateway(1, 0, 0)
    node = Node(1, 0.0, 0.0, 7, 14, class_type="C")
    t = scheduler.schedule_class_c(node, 1.0, b"b", gw)
    assert math.isclose(t, 1.5)
    frame, gw2 = scheduler.pop_ready(node.id, t)
    assert frame == b"b" and gw2 is gw
