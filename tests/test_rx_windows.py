import math

from simulateur_lora_sfrd.launcher.node import Node
from simulateur_lora_sfrd.launcher.server import NetworkServer
from simulateur_lora_sfrd.launcher.gateway import Gateway
from simulateur_lora_sfrd.launcher.lorawan import compute_rx1, compute_rx2


def test_schedule_receive_windows():
    node = Node(1, 0.0, 0.0, 7, 14)
    node.rx_delay = 2.0
    end_time = 10.0

    rx1, rx2 = node.schedule_receive_windows(end_time)

    assert math.isclose(rx1, compute_rx1(end_time, node.rx_delay))
    assert math.isclose(rx2, compute_rx2(end_time, node.rx_delay))


def test_send_downlink_schedules_in_rx_window():
    server = NetworkServer()
    gw = Gateway(0, 0, 0)
    node = Node(0, 0.0, 0.0, 7, 14)
    server.gateways = [gw]
    server.nodes = [node]

    node.last_uplink_end_time = 5.0
    server.send_downlink(node, b"x")

    t = server.scheduler.next_time(node.id)
    rx1 = compute_rx1(node.last_uplink_end_time, node.rx_delay)
    rx2 = compute_rx2(node.last_uplink_end_time, node.rx_delay)

    assert math.isclose(t, rx1) or math.isclose(t, rx2)
