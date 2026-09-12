"""Secuenciación exacta de paradas (Held-Karp, <=12 paradas). No se aprende — ai/CLAUDE.md §2.1."""

from __future__ import annotations


def held_karp(stops, t0, pos0, travel_fn, constraints) -> tuple[list[int] | None, float, float]:
    """Devuelve (orden_óptimo, tiempo_total, distancia_total).
    Si no existe secuencia factible devuelve (None, inf, inf)."""
    raise NotImplementedError
