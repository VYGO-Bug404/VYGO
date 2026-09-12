"""B0 aleatoria, B_SERIAL (una app, sin agrupamiento), B1 acepta-primera-factible, B2 umbral
(con y sin p_gana). ai/CLAUDE.md §9, docs/vygo-ai-training.md §6.1. B_SERIAL es el
repartidor SIN VYGO hoy (una sola app, un pedido a la vez); B1 es el "baseline simple" del
reto (comportamiento FIFO pero con agrupamiento ya permitido); B2 es el serio (regla de
umbral, docs/modelo-matematico.md §4.6); B2-ingenuo es B2 sin el factor p_gana, para medir
cuánto vale entender la competencia.
"""

from __future__ import annotations

import math

import numpy as np

from vygo.feasibility import CONTADOR_MOTIVOS, K_F, action_mask
from vygo.insertion import EstadoRuta, eval_insertion
from vygo.sequencer import n_pedidos_en_plan

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


def politica_serial(estado: EstadoRuta) -> int:
    """B_SERIAL: el repartidor SIN VYGO -- una sola app, sin agrupamiento. Igual que B1
    (acepta la primera oferta factible) pero nunca lleva más de un pedido en curso: mientras
    el plan activo ya tenga >=1 pedido, rechaza todo hasta entregarlo.

    Impuesto aquí, a nivel de POLÍTICA, sin tocar `feasibility.K_A_MAXIMO` (sigue en 4 para
    el entorno y para B1/B2 -- esta tarea pidió explícitamente no tocar el entorno). El
    efecto es idéntico al de correr con K_A_MAXIMO=1: el entorno seguiría permitiendo hasta
    4, pero esta política nunca pide más de 1."""

    if n_pedidos_en_plan(estado.plan) >= 1:
        return K_F
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


def politica_umbral(
    estado: EstadoRuta, rho_hat: float, con_p_gana: bool = True, instrumentar: bool = False,
) -> int:
    """B2 (con_p_gana=True) / B2-ingenuo (con_p_gana=False): entre las ofertas factibles,
    maximiza p_gana_j * (precio_j - c_kappa*delta_dist_j) / delta_t_j y acepta esa oferta
    si supera `rho_hat`; si ninguna supera el umbral, rechazar_todas.

    `instrumentar`: ver `feasibility.action_mask`. Aquí además se suman al mismo contador
    global las categorías "umbral_rho" (factible pero su tasa marginal no superó `rho_hat`)
    y "aceptada" (la oferta finalmente elegida), sólo cuando el plan activo ya tiene >=1
    pedido -- la máscara sola no puede distinguir estas dos, sólo la política lo sabe."""

    mask = action_mask(estado, instrumentar=instrumentar)
    n_pedidos_plan = n_pedidos_en_plan(estado.plan)
    diag_activo = instrumentar and n_pedidos_plan >= 1

    candidatas: list[tuple[int, float]] = []
    for i in range(K_F):
        if not mask[i]:
            continue
        tasa, ok = _tasa_marginal(estado, i, con_p_gana)
        if ok:
            candidatas.append((i, tasa))

    mejor_i, mejor_tasa = None, rho_hat
    for i, tasa in candidatas:
        if tasa > mejor_tasa:
            mejor_tasa, mejor_i = tasa, i

    if diag_activo:
        for i, _tasa in candidatas:
            if i != mejor_i:
                CONTADOR_MOTIVOS["umbral_rho"] += 1
        if mejor_i is not None:
            CONTADOR_MOTIVOS["aceptada"] += 1

    return mejor_i if mejor_i is not None else K_F
