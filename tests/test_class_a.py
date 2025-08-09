import math
from types import SimpleNamespace

from simulateur_lora_sfrd.launcher.downlink_scheduler import DownlinkScheduler
from simulateur_lora_sfrd.launcher.gateway import Gateway
from simulateur_lora_sfrd.launcher.node import Node
from simulateur_lora_sfrd.launcher.server import NetworkServer
from simulateur_lora_sfrd.launcher.lorawan import compute_rx2


def test_schedule_class_a():
    scheduler = DownlinkScheduler()
    gw = Gateway(1, 0, 0)
    node = Node(1, 0.0, 0.0, 7, 14)
    t = scheduler.schedule_class_a(node, 0.0, 1.0, 2.0, b"a", gw)
    assert math.isclose(t, 1.0)
    frame, gw2 = scheduler.pop_ready(node.id, t)
    assert frame == b"a" and gw2 is gw


def test_schedule_class_a_after_delay():
    scheduler = DownlinkScheduler()
    gw = Gateway(1, 0, 0)
    node = Node(1, 0.0, 0.0, 7, 14)
    scheduler._gateway_busy[gw.id] = 1.5
    t = scheduler.schedule_class_a(node, 0.0, 1.0, 2.0, b"b", gw)
    assert math.isclose(t, 2.0)
    frame, gw2 = scheduler.pop_ready(node.id, t)
    assert frame == b"b" and gw2 is gw


def test_downlink_with_server_delays():
    sim = SimpleNamespace(current_time=0.0, event_queue=[], event_id_counter=0)
    server = NetworkServer(simulator=sim, process_delay=1.0, network_delay=1.0)
    gw = Gateway(0, 0, 0)
    server.gateways = [gw]
    node = Node(0, 0, 0, 7, 14)
    server.nodes = [node]

    server.schedule_receive(1, node.id, gw.id, -40, at_time=0.0)
    evt = sim.event_queue.pop(0)
    sim.current_time = evt.time
    server._handle_network_arrival(evt.id)
    evt = sim.event_queue.pop(0)
    sim.current_time = evt.time
    server._process_scheduled(evt.id)

    server.send_downlink(node, b"x")
    t = server.scheduler.next_time(node.id)
    expected = compute_rx2(0.0, node.rx_delay) + server.network_delay
    assert math.isclose(t, expected)

