"""Máscara de factibilidad exacta (frescura, capacidad, precedencia). ai/CLAUDE.md §2.2.

violaciones_frescura debe ser 0 SIEMPRE: si no lo es, es un bug de esta máscara, no un
problema de entrenamiento. Enmascarar (no penalizar) es la diferencia entre un agente que
aprende y uno que no (docs/modelo-matematico.md §4.4): el gradiente de la acción
enmascarada es exactamente cero, sin sesgo.

TOPE DURO K_A: el plan activo nunca pasa de `K_A_MAXIMO` pedidos (mismo número que el
umbral exacto de `sequencer.held_karp`) -- con 5 pedidos la enumeración exacta salta de
2520 a 113400 secuencias. Con el plan lleno, TODAS las ofertas se marcan infactibles sin
siquiera evaluarlas.

PREFILTRO: de las hasta K_F=8 ofertas visibles, sólo se calendarizan (con `eval_insertion`,
ya barato desde el patch de inserción) las `N_PREFILTRO` mejores por un puntaje BARATÍSIMO
(desvío en línea recta / tarifa, sin calendarizar nada). Las demás se marcan infactibles
directamente ("descartadas por prefiltro") -- el agente las sigue viendo en la observación
con sus features baratos (delta, tarifa, anillo, p_gana), sólo que el mask no les da la
oportunidad de aceptarse ese step.
"""

from __future__ import annotations

import math

import numpy as np

from vygo.insertion import EstadoRuta, OfertaCandidata, baseline_plan, eval_insertion
from vygo.sequencer import UMBRAL_EXACTO_PEDIDOS, verificar_y_calendarizar

K_F = 8
K_A_MAXIMO = UMBRAL_EXACTO_PEDIDOS
N_PREFILTRO = 3
HOLGURA_MINIMA_REPOSICIONAR_S = 5 * 60.0


def holguras_frescura_plan(estado: EstadoRuta) -> list[float]:
    """Holgura de frescura (theta_i - (T_entrega - S_recogida)) de cada pedido del plan
    activo que tenga theta definido, según el calendario real (con cualquier espera
    estratégica ya aplicada) de la secuencia vigente del plan."""

    if not estado.plan:
        return []

    orden, _tiempo, _dist, _exacto, _evaluadas = baseline_plan(estado)
    if orden is None:
        return []

    resultado = verificar_y_calendarizar(
        orden, estado.plan, estado.t, estado.pos, estado.travel_fn, estado.restricciones,
    )
    if resultado is None:
        return []
    llegadas, salidas, _dist_total = resultado

    pos_recogida: dict[str, int] = {}
    pos_entrega: dict[str, int] = {}
    for k, idx in enumerate(orden):
        parada = estado.plan[idx]
        if parada.tipo == "recogida":
            pos_recogida[parada.id] = k
        else:
            pos_entrega[parada.id] = k

    holguras = []
    for pid, k_e in pos_entrega.items():
        theta = estado.restricciones.theta_de(pid)
        if theta is None:
            continue
        k_r = pos_recogida[pid]
        holguras.append(theta - (llegadas[k_e] - salidas[k_r]))
    return holguras


def _puntaje_prefiltro(oferta: OfertaCandidata, estado: EstadoRuta) -> float:
    """Desvío en línea recta (celdas) / tarifa. Menor es mejor. Cero calendarización: sólo
    geometría directa sobre las posiciones, para poder ordenar las 8 ofertas sin pagar
    ni siquiera la inserción barata en las 5 que no van a calendarizarse."""

    dist_recogida = math.hypot(
        estado.pos[0] - oferta.pos_recogida[0], estado.pos[1] - oferta.pos_recogida[1],
    )
    dist_entrega = math.hypot(
        oferta.pos_recogida[0] - oferta.pos_entrega[0], oferta.pos_recogida[1] - oferta.pos_entrega[1],
    )
    precio = oferta.precio if oferta.precio else 1.0
    return (dist_recogida + dist_entrega) / max(precio, 1e-6)


def action_mask(estado: EstadoRuta) -> np.ndarray:
    """Shape (K_F + 2,), dtype bool. K_F=8 ofertas visibles, luego rechazar_todas,
    reposicionarse (ai/CLAUDE.md §6)."""

    mask = np.zeros(K_F + 2, dtype=bool)
    n_pedidos_plan = len(estado.plan) // 2

    if n_pedidos_plan < K_A_MAXIMO:
        candidatos = []
        for i in range(K_F):
            oferta = estado.ofertas[i] if i < len(estado.ofertas) else None
            if oferta is None:
                continue
            if oferta.expira_en is not None and oferta.expira_en <= estado.t:
                continue
            candidatos.append((i, oferta))

        candidatos.sort(key=lambda par: _puntaje_prefiltro(par[1], estado))
        for i, oferta in candidatos[:N_PREFILTRO]:
            _dt, _dd, factible = eval_insertion(estado.plan, oferta, estado)
            mask[i] = factible
        # candidatos[N_PREFILTRO:] queda en False: descartadas por prefiltro, no evaluadas.
    # n_pedidos_plan >= K_A_MAXIMO: tope duro, ninguna oferta es factible (mask ya en False).

    mask[K_F] = True  # rechazar_todas: siempre disponible

    holguras = holguras_frescura_plan(estado)
    mask[K_F + 1] = not any(h < HOLGURA_MINIMA_REPOSICIONAR_S for h in holguras)

    return mask
