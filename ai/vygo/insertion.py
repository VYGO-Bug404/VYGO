"""Δt_j, Δδ_j óptimos por oferta al insertarla en el plan activo: corre held_karp sobre el
plan solo y sobre plan+oferta, y devuelve la diferencia. El resultado de held_karp(plan) se
cachea en `estado` para que evaluar varias ofertas contra el mismo plan (como hace
feasibility.action_mask con 8 ofertas) no repita el cálculo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from vygo.schema import Clima
from vygo.sequencer import Parada, Restricciones, TravelFn, held_karp

_MAX_STOPS_TOTAL = 12


@dataclass(slots=True, frozen=True)
class OfertaCandidata:
    """Oferta candidata a insertar: no es el espejo de BD `schema.Oferta` (esa mira la fila
    de `ofertas_pedido`); esta trae justo lo que el secuenciador necesita del PEDIDO detrás
    de la oferta."""

    id: str
    pos_recogida: tuple[int, int]
    pos_entrega: tuple[int, int]
    r: float
    l: Optional[float]
    theta: Optional[float]
    carga: int = 1
    expira_en: Optional[float] = None


@dataclass(slots=True)
class EstadoRuta:
    """Snapshot mínimo que insertion.py y feasibility.py necesitan del vehículo + plan activo
    + ofertas visibles (S_k del SMDP, ai/CLAUDE.md / docs/modelo-matematico.md §4.2)."""

    t: float
    pos: tuple[int, int]
    clima: Clima
    plan: list[Parada]
    restricciones: Restricciones
    travel_fn: TravelFn
    ofertas: list[Optional[OfertaCandidata]] = field(default_factory=list)
    cache: dict = field(default_factory=dict)


def _clave_plan(plan: list[Parada], t: float) -> tuple:
    return (round(t, 3), tuple((p.id, p.tipo) for p in plan))


def baseline_plan(estado: EstadoRuta) -> tuple[list[int] | None, float, float]:
    """held_karp(estado.plan) solo, cacheado en estado.cache. Pública para que
    feasibility.py reuse el mismo resultado (evita recalcular por cada una de las hasta 8
    ofertas Y por el chequeo de holgura de frescura del propio plan)."""

    clave = _clave_plan(estado.plan, estado.t)
    if clave not in estado.cache:
        stops = [{"id": p.id, "tipo": p.tipo, "pos": p.pos} for p in estado.plan]
        estado.cache[clave] = held_karp(stops, estado.t, estado.pos, estado.travel_fn, estado.restricciones)
    return estado.cache[clave]


def _restricciones_con_oferta(restricciones: Restricciones, oferta: OfertaCandidata) -> Restricciones:
    return Restricciones(
        capacidad=restricciones.capacidad,
        r={**restricciones.r, oferta.id: oferta.r},
        l={**restricciones.l, oferta.id: oferta.l},
        theta={**restricciones.theta, oferta.id: oferta.theta},
        carga={**restricciones.carga, oferta.id: oferta.carga},
    )


def eval_insertion(
    plan: list[Parada], oferta: OfertaCandidata, estado: EstadoRuta,
) -> tuple[float, float, bool]:
    """Devuelve (delta_t_segundos, delta_dist_metros, factible)."""

    if len(plan) + 2 > _MAX_STOPS_TOTAL:
        return math.inf, math.inf, False

    _orden_base, tiempo_base, dist_base = baseline_plan(estado)
    if _orden_base is None and plan:
        # El plan activo ya comprometido debería ser siempre factible por invariante; si no
        # lo es, no hay una base contra la cual medir el delta.
        return math.inf, math.inf, False
    if not plan:
        tiempo_base, dist_base = 0.0, 0.0

    stops_combinado = [{"id": p.id, "tipo": p.tipo, "pos": p.pos} for p in plan]
    stops_combinado.append({"id": oferta.id, "tipo": "recogida", "pos": oferta.pos_recogida})
    stops_combinado.append({"id": oferta.id, "tipo": "entrega", "pos": oferta.pos_entrega})
    restricciones_combinadas = _restricciones_con_oferta(estado.restricciones, oferta)

    orden_nuevo, tiempo_nuevo, dist_nuevo = held_karp(
        stops_combinado, estado.t, estado.pos, estado.travel_fn, restricciones_combinadas,
    )
    if orden_nuevo is None:
        return math.inf, math.inf, False

    return tiempo_nuevo - tiempo_base, dist_nuevo - dist_base, True
