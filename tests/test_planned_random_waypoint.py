import pytest

from loraflexsim.launcher.planned_random_waypoint import PlannedRandomWaypoint
from loraflexsim.launcher.node import Node


def test_planner_avoids_high_obstacle():
    terrain = [
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
    ]
    heights = [
        [0, 0, 0],
        [0, 10, 0],
        [0, 0, 0],
    ]
    mobility = PlannedRandomWaypoint(
        area_size=90.0,
        terrain=terrain,
        obstacle_height_map=heights,
        max_height=5,
        seed=123,
    )
    node = Node(1, 0.0, 0.0, 7, 14)
    mobility.assign(node)
    cells = [mobility.planner._coord_to_cell(x, y) for x, y in node.path]
    assert (1, 1) not in cells


def test_assign_sets_path():
    terrain = [[1, 1], [1, 1]]
    mobility = PlannedRandomWaypoint(area_size=20.0, terrain=terrain, seed=123)
    node = Node(1, 5.0, 5.0, 7, 14)
    mobility.assign(node)
    assert len(node.path) >= 2


def test_move_consumes_residual_distance_after_new_path():
    terrain = [[1, 1], [1, 1]]

    class StubPlanner:
        def __init__(self):
            self.paths = [
                [(5.0, 5.0), (15.0, 5.0)],
                [(15.0, 5.0), (15.0, 10.0), (20.0, 10.0)],
            ]

        def random_free_point(self):
            if self.paths:
                return self.paths[0][-1]
            return (20.0, 10.0)

        def find_path(self, start, goal):
            if self.paths:
                return self.paths.pop(0)
            return [start, goal]

        def elevation_at(self, x, y):
            return 0.0

    mobility = PlannedRandomWaypoint(area_size=20.0, terrain=terrain, seed=0)
    mobility.planner = StubPlanner()
    node = Node(1, 5.0, 5.0, 7, 14)
    mobility.assign(node)
    node.speed = 3.0
    node.last_move_time = 0.0

    mobility.move(node, current_time=5.0)

    assert node.x == pytest.approx(15.0)
    assert node.y == pytest.approx(10.0)
    assert node.path_index == 1
    assert node.path[0] == (15.0, 5.0)
    assert node.last_move_time == pytest.approx(5.0)
