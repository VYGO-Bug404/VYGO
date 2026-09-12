"""Máscara de factibilidad exacta (frescura, capacidad, precedencia). ai/CLAUDE.md §2.2.

violaciones_frescura debe ser 0 SIEMPRE: si no lo es, es un bug de esta máscara, no un
problema de entrenamiento. Enmascarar (no penalizar) es la diferencia entre un agente que
aprende y uno que no (docs/modelo-matematico.md §4.4): el gradiente de la acción
enmascarada es exactamente cero, sin sesgo.
"""

from __future__ import annotations

import numpy as np

from vygo.insertion import EstadoRuta, baseline_plan, eval_insertion
from vygo.sequencer import verificar_y_calendarizar

K_F = 8
HOLGURA_MINIMA_REPOSICIONAR_S = 5 * 60.0


def _holguras_frescura(estado: EstadoRuta) -> list[float]:
    """Holgura de frescura (theta_i - (T_entrega - S_recogida)) de cada pedido del plan
    activo que tenga theta definido, según el calendario real (con cualquier espera
    estratégica ya aplicada) de la secuencia óptima del plan."""

    if not estado.plan:
        return []

    orden, _tiempo, _dist = baseline_plan(estado)
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


def action_mask(estado: EstadoRuta) -> np.ndarray:
    """Shape (K_F + 2,), dtype bool. K_F=8 ofertas visibles, luego rechazar_todas,
    reposicionarse (ai/CLAUDE.md §6)."""

    mask = np.zeros(K_F + 2, dtype=bool)

    for i in range(K_F):
        oferta = estado.ofertas[i] if i < len(estado.ofertas) else None
        if oferta is None:
            continue
        if oferta.expira_en is not None and oferta.expira_en <= estado.t:
            continue
        _dt, _dd, factible = eval_insertion(estado.plan, oferta, estado)
        mask[i] = factible

    mask[K_F] = True  # rechazar_todas: siempre disponible

    holguras = _holguras_frescura(estado)
    mask[K_F + 1] = not any(h < HOLGURA_MINIMA_REPOSICIONAR_S for h in holguras)

    return mask
