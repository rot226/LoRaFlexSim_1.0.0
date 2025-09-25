import math

from loraflexsim.launcher.downlink_scheduler import DownlinkScheduler
from loraflexsim.launcher.gateway import Gateway
from loraflexsim.launcher.lorawan import next_beacon_time
from loraflexsim.launcher.node import Node


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


def test_next_beacon_time_with_drift():
    interval = 128.0
    drift = 20e-6
    first = next_beacon_time(interval - 1e-3, interval, last_beacon=0.0, drift=drift)
    assert math.isclose(first, interval * (1.0 + drift), rel_tol=1e-9)
    second = next_beacon_time(first - 1e-3, interval, last_beacon=first, drift=drift)
    assert math.isclose(second, first + interval * (1.0 + drift), rel_tol=1e-9)


def test_next_beacon_time_after_successive_losses():
    interval = 128.0
    drift = 50e-6
    after = interval * 3.4
    expected = math.ceil((after + 1e-9) / interval) * interval
    t = next_beacon_time(after, interval, last_beacon=0.0, drift=drift)
    assert math.isclose(t, expected, rel_tol=1e-9)


def test_node_clock_offset_after_missed_beacons():
    interval = 128.0
    drift = 30e-6
    node = Node(1, 0.0, 0.0, 7, 14, class_type="B", beacon_drift=drift)
    node.clock_offset = 0.0
    node.miss_beacon(interval)
    assert math.isclose(node.clock_offset, interval * drift, rel_tol=1e-9)
    node.miss_beacon(interval)
    assert math.isclose(node.clock_offset, 2 * interval * drift, rel_tol=1e-9)
