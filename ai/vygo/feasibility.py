"""Máscara de factibilidad exacta (frescura, capacidad, precedencia). ai/CLAUDE.md §2.2.

violaciones_frescura debe ser 0 SIEMPRE una vez implementado: si no lo es, es un bug de
esta máscara, no un problema de entrenamiento.
"""

from __future__ import annotations

import numpy as np


def action_mask(estado) -> np.ndarray:
    """Shape (K_F + 2,), dtype bool."""
    raise NotImplementedError
