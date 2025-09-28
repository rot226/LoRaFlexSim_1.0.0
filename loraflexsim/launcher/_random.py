"""Utilitaires pour initialiser des générateurs pseudo-aléatoires contrôlés."""

from __future__ import annotations

from typing import Sequence

import numpy as np


SeedLike = int | Sequence[int] | None


def ensure_rng(
    rng: np.random.Generator | None, seed: SeedLike = 0
) -> np.random.Generator:
    """Retourne un :class:`~numpy.random.Generator` déterministe.

    Si ``rng`` est fourni il est retourné tel quel, sinon un nouveau générateur
    ``numpy.random.Generator`` basé sur ``numpy.random.MT19937`` est construit
    en utilisant ``seed``. Lorsque ``seed`` vaut ``None`` un générateur non
    déterministe est créé.
    """

    if rng is not None:
        return rng
    bitgen = np.random.MT19937() if seed is None else np.random.MT19937(seed)
    return np.random.Generator(bitgen)


__all__ = ["SeedLike", "ensure_rng"]

