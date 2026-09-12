"""B0 aleatoria, B1 acepta-primera-factible, B2 umbral (con y sin p_gana). ai/CLAUDE.md §9,
docs/vygo-ai-training.md §6.1. B1 es el "baseline simple" del reto (comportamiento FIFO de
un repartidor novato); B2 es el serio (regla de umbral, docs/modelo-matematico.md §4.6);
B2-ingenuo es B2 sin el factor p_gana, para medir cuánto vale entender la competencia.
"""

from __future__ import annotations

import math

import numpy as np

from vygo.feasibility import K_F, action_mask
from vygo.insertion import EstadoRuta, eval_insertion

COSTO_KM_MXN = 1.2


class RhoHatMovil:
    """Media móvil de la tasa de ganancia realizada sobre una ventana de tiempo simulado
    (default 90 min), inicializada en `inicial` MXN/h. Distinta del EMA (alfa=0.01) que usa
    VygoEnv internamente para la recompensa: B2 es una política externa y lleva su propia
    estimación, tal como la llevaría un repartidor real mirando su ingreso reciente."""

    def __init__(self, ventana_s: float = 90 * 60.0, inicial: float = 100.0) -> None:
        self.ventana_s = ventana_s
        self.valor = inicial
        self._eventos: list[tuple[float, float]] = []

    def actualizar(self, t: float, ingreso: float) -> None:
        self._eventos.append((t, ingreso))
        corte = t - self.ventana_s
        while self._eventos and self._eventos[0][0] < corte:
            self._eventos.pop(0)
        total = sum(g for _, g in self._eventos)
        horas = min(t, self.ventana_s) / 3600.0
        if horas > 0:
            self.valor = total / horas


def politica_aleatoria(estado: EstadoRuta, rng: np.random.Generator) -> int:
    """B0: acción uniforme entre las que la máscara permite. Piso absoluto."""
    mask = action_mask(estado)
    validas = np.flatnonzero(mask)
    return int(rng.choice(validas)) if len(validas) else K_F


def politica_primera_factible(estado: EstadoRuta) -> int:
    """B1: acepta la primera oferta factible en orden de slot; si ninguna, rechazar_todas."""
    mask = action_mask(estado)
    for i in range(K_F):
        if mask[i]:
            return i
    return K_F


def _tasa_marginal(estado: EstadoRuta, i: int, con_p_gana: bool) -> tuple[float, bool]:
    oferta = estado.ofertas[i]
    if oferta is None:
        return -math.inf, False
    delta_t, delta_dist, factible = eval_insertion(estado.plan, oferta, estado)
    if not factible or delta_t <= 0:
        return -math.inf, False
    valor_marginal = (oferta.precio or 0.0) - COSTO_KM_MXN * (delta_dist / 1000.0)
    tasa = valor_marginal / (delta_t / 3600.0)
    if con_p_gana:
        tasa *= oferta.p_gana_estimada if oferta.p_gana_estimada is not None else 1.0
    return tasa, True


def politica_umbral(estado: EstadoRuta, rho_hat: float, con_p_gana: bool = True) -> int:
    """B2 (con_p_gana=True) / B2-ingenuo (con_p_gana=False): entre las ofertas factibles,
    maximiza p_gana_j * (precio_j - c_kappa*delta_dist_j) / delta_t_j y acepta esa oferta
    si supera `rho_hat`; si ninguna supera el umbral, rechazar_todas."""

    mask = action_mask(estado)
    mejor_i, mejor_tasa = None, rho_hat
    for i in range(K_F):
        if not mask[i]:
            continue
        tasa, ok = _tasa_marginal(estado, i, con_p_gana)
        if ok and tasa > mejor_tasa:
            mejor_tasa, mejor_i = tasa, i
    return mejor_i if mejor_i is not None else K_F
