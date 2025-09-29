import math

from loraflexsim.launcher.random_waypoint import RandomWaypoint
from loraflexsim.launcher.node import Node


def test_random_waypoint_move_within_bounds_and_updates_time():
    mobility = RandomWaypoint(
        area_size=100.0, min_speed=1.0, max_speed=1.0, seed=42
    )
    node = Node(0, 50.0, 50.0, 7, 14)

    mobility.assign(node)
    mobility.move(node, 10.0)

    assert 0.0 <= node.x <= 100.0
    assert 0.0 <= node.y <= 100.0
    assert node.last_move_time == 10.0


def test_reassign_preserves_last_move_time_and_bounds_movement():
    mobility = RandomWaypoint(
        area_size=100.0, min_speed=1.0, max_speed=1.0, seed=123
    )
    node = Node(1, 60.0, 40.0, 8, 14)

    mobility.assign(node)
    mobility.move(node, 10.0)
    first_x, first_y = node.x, node.y
    assert node.last_move_time == 10.0

    mobility.assign(node)
    assert node.last_move_time == 10.0

    mobility.move(node, 12.0)

    distance = math.hypot(node.x - first_x, node.y - first_y)
    assert distance <= mobility.max_speed * (12.0 - 10.0) + 1e-9
    assert 0.0 <= node.x <= 100.0
    assert 0.0 <= node.y <= 100.0
    assert node.last_move_time == 12.0
