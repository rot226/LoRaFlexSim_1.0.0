import random
from simulateur_lora_sfrd.launcher.terrain_mobility import TerrainMapMobility
from simulateur_lora_sfrd.launcher.node import Node


def test_terrain_mobility_path_avoids_obstacle():
    terrain = [
        [1, -1],
        [1, 1],
    ]
    mobility = TerrainMapMobility(area_size=100.0, terrain=terrain)
    node = Node(1, 0.0, 0.0, 7, 14)
    random.seed(0)
    mobility.assign(node)
    # Path should not go through cell (1,0) which is an obstacle
    cells = [mobility._coord_to_cell(x, y) for x, y in node.path]
    assert (1, 0) not in cells

