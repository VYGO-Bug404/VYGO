"""Δt_j, Δδ_j óptimos por oferta al insertarla en el plan activo."""

from __future__ import annotations


def eval_insertion(plan, oferta, estado) -> tuple[float, float, bool]:
    """Devuelve (delta_t_segundos, delta_dist_metros, factible)."""
    raise NotImplementedError
