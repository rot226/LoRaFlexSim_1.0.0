from __future__ import annotations

import hashlib
import random
import secrets
# Use a regular set instead of WeakSet because numpy.random.Generator
# does not support weak references in some numpy versions.
import numpy as np
from typing import Dict, Tuple


class UncontrolledRandomError(RuntimeError):
    """Raised when an unmanaged RNG source is accessed."""


class RngManager:
    """Manage deterministic RNG streams based on MT19937."""

    def __init__(self, master_seed: int) -> None:
        self.master_seed = master_seed
        self._streams: Dict[Tuple[str, int], np.random.Generator] = {}

    def get_stream(self, stream_name: str, node_id: int = 0) -> np.random.Generator:
        """Return a Generator instance for the given stream and node."""
        key = (stream_name, node_id)
        if key not in self._streams:
            # ``hash()`` is not stable across interpreter runs so we
            # derive a deterministic hash from the stream name instead.
            digest = hashlib.sha256(stream_name.encode()).digest()
            stream_hash = int.from_bytes(digest[:8], "little")
            seed = (self.master_seed ^ stream_hash ^ node_id) & 0xFFFFFFFF
            gen = np.random.Generator(np.random.MT19937(seed))
            register_stream(gen)
            self._streams[key] = gen
        return self._streams[key]


_allowed_generators: "set[np.random.Generator]" = set()
_hook_enabled = False
_orig_random_funcs: dict[str, object] = {}
_orig_numpy_methods: dict[str, object] = {}
_orig_secret_funcs: dict[str, object] = {}


def register_stream(gen: np.random.Generator) -> None:
    """Mark ``gen`` as an allowed RNG stream."""

    _allowed_generators.add(gen)


def _reject(*_: object, **__: object) -> None:
    raise UncontrolledRandomError(
        "Unmanaged random source: use RngManager.get_stream()"
    )


def activate_global_hooks() -> None:
    """Globally reject uncontrolled RNG usage."""

    global _hook_enabled
    if _hook_enabled:
        return
    _hook_enabled = True

    for name in [
        "random",
        "randrange",
        "randint",
        "choice",
        "shuffle",
        "uniform",
        "gauss",
        "betavariate",
        "expovariate",
        "gammavariate",
        "lognormvariate",
        "normalvariate",
        "paretovariate",
        "weibullvariate",
        "sample",
        "choices",
    ]:
        if hasattr(random, name):
            _orig_random_funcs[name] = getattr(random, name)
            setattr(random, name, _reject)

    def wrap(method):
        def wrapper(self, *a, **k):
            if self not in _allowed_generators:
                _reject()
            return method(self, *a, **k)

        return wrapper

    for name in ["random", "normal", "choice", "integers", "shuffle"]:
        if hasattr(np.random.Generator, name):
            orig = getattr(np.random.Generator, name)
            _orig_numpy_methods[name] = orig
            setattr(np.random.Generator, name, wrap(orig))

    for name in [
        "choice",
        "randbelow",
        "randbits",
        "token_bytes",
        "token_hex",
        "token_urlsafe",
    ]:
        if hasattr(secrets, name):
            _orig_secret_funcs[name] = getattr(secrets, name)
            setattr(secrets, name, _reject)


def deactivate_global_hooks() -> None:
    """Restore modules to their original state."""

    global _hook_enabled
    if not _hook_enabled:
        return

    for name, func in _orig_random_funcs.items():
        setattr(random, name, func)
    _orig_random_funcs.clear()

    for name, method in _orig_numpy_methods.items():
        setattr(np.random.Generator, name, method)
    _orig_numpy_methods.clear()

    for name, func in _orig_secret_funcs.items():
        setattr(secrets, name, func)
    _orig_secret_funcs.clear()

    _hook_enabled = False
