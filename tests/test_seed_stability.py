import hashlib
import struct

from traffic.rng_manager import RngManager
from simulateur_lora_sfrd.launcher.node import Node


def _intervals_hash(seed: int, mean_interval: float = 1.0, count: int = 10000) -> str:
    rng = RngManager(seed).get_stream("traffic", 0)
    node = Node(0, 0, 0, 7, 14)
    node.ensure_poisson_arrivals(
        1e9, mean_interval, rng, min_interval=0.0, limit=count
    )
    h = hashlib.sha256()
    last = 0.0
    for t in node.arrival_queue:
        h.update(struct.pack("<d", t - last))
        last = t
    return h.hexdigest()


def test_seed_reproducibility():
    seed = 42
    hashes = [_intervals_hash(seed) for _ in range(10)]
    assert len(set(hashes)) == 1

