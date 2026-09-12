"""VygoEnv: entorno gymnasium L0/L1/L2.

La red sólo decide aceptar/rechazar/reposicionar; secuenciación (Held-Karp) y restricciones
duras (máscara de factibilidad) no se aprenden — ai/CLAUDE.md §2. NumPy puro en L0/L1,
objetivo >=5000 steps/s con 16 entornos en paralelo.
"""

from __future__ import annotations

import gymnasium


class VygoEnv(gymnasium.Env):
    """obs: Box(float32); action: Discrete(K_F + 2)
    K_F = 8 ofertas visibles; acción K_F = rechazar-todas; K_F+1 = reposicionarse."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError
