"""B0 aleatoria, B1 acepta-todo, B2 regla de umbral, B3 MILP en horizonte rodante.

Ver ai/CLAUDE.md §5 (firma de politica_umbral) y docs/vygo-ai-training.md §6.1.
"""

from __future__ import annotations


def politica_umbral(estado, rho_hat) -> int:
    """B2: acepta la oferta j si (Δf_j - c_kappa*Δδ_j - ΔΨ_j) / Δt_j > rho_hat."""
    raise NotImplementedError
