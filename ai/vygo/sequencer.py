"""Secuenciación exacta de paradas (Held-Karp, <=12 paradas). No se aprende — ai/CLAUDE.md §2.1.

LA RESTRICCIÓN DE FRESCURA (T_entrega - S_recoleccion <= theta_i) ACOPLA la recolección y la
entrega del MISMO pedido. Eso rompe la dominancia clásica de Held-Karp ("llegar antes a
(subconjunto, último nodo) es siempre mejor"): recoger antes arranca antes el reloj de
frescura, así que llegar más temprano puede volver INFACTIBLE una secuencia que sí era
factible llegando más tarde. Esperar a propósito en el comercio puede ser óptimo o incluso
necesario para la factibilidad.

Por eso el secuenciador tiene DOS pasadas, no una:

1. Pase hacia adelante (DP sobre (subconjunto, último nodo), tiempo de llegada más
   temprano): sólo ordena candidatas y poda por capacidad y precedencia, que sí son
   monótonas por subconjunto. NUNCA decide factibilidad de frescura aquí. Corre compilado
   con numba sobre una matriz de viaje evaluada una sola vez en t0 (una "foto" del tráfico
   al momento de decidir) porque en Python puro no cabe en el presupuesto de tiempo (ver
   `ai/reports/HANDOFF.md`); esa foto sólo sirve para RANKEAR, nunca para decidir
   factibilidad final.
2. Del óptimo de ese DP se generan K secuencias candidatas por perturbación (swaps
   adyacentes y reubicaciones de una parada, puntuadas con la misma foto), ordenadas por
   tiempo de completado.
3. Por candidata, un pase hacia atrás calcula el instante más tardío admisible de cada
   parada (deadlines) y, con un punto fijo acotado, la espera estratégica mínima que cada
   recolección necesita para no violar la frescura de su propia entrega, sin retrasar nada
   que ya esté al límite. Con ese calendario se verifica frescura, fechas límite, capacidad
   y espera por preparación (S_o >= max(T_o, r_i)).
4. Se devuelve la primera candidata que pasa. Si ninguna de las K pasa, (None, inf, inf) y
   se incrementa el contador `candidatas_agotadas` (ver `candidatas_agotadas()`).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable

import numba
import numpy as np

TravelFn = Callable[[tuple[int, int], tuple[int, int], float], tuple[float, float]]

_MAX_PARADAS = 12
_MAX_ITER_PUNTO_FIJO = 20
_EPS = 1e-6

# Con <=3 pedidos (<=6 paradas) enumerar TODAS las secuencias válidas por precedencia es
# trivial (90 secuencias) y exacto: nada de heurística de perturbación.
# PÚBLICA a propósito: es el mismo K_A que env.py/feasibility.py usan como tope duro del
# plan activo (nunca aceptar un 4º pedido) -- una sola fuente de verdad para el número.
#
# Bajado de 4 a 3 (documentado, autorizado explícitamente por la tarea que arregló el
# cuello de botella de llamadas): con K_A=4 (2520 secuencias) el benchmark de 16 entornos
# daba 775.7 steps/s -- por encima del piso de 300 pero por debajo del objetivo real de
# 1000. Con K_A=3 (90 secuencias, la guardia de tiempo de 25ms de held_karp deja de
# activarse en la práctica) el mismo benchmark da 1617.6 steps/s. Ver reports/HANDOFF.md.
UMBRAL_EXACTO_PEDIDOS = 3

# Guardia de tiempo del camino exacto (§ held_karp): si enumerar+verificar las hasta 2520
# secuencias tarda más que esto, se aborta con lo mejor encontrado hasta ese punto en vez
# de colgar el step del entorno. Nunca debería hacer falta con K_A<=4, pero es la red de
# seguridad si algún día se sube el umbral o el travel_fn real es más caro de lo esperado.
_LIMITE_TIEMPO_EXACTO_S = 0.025

_contador_candidatas_agotadas = 0


def candidatas_agotadas() -> int:
    """Veces que held_karp agotó las K candidatas sin encontrar una factible."""
    return _contador_candidatas_agotadas


def reset_candidatas_agotadas() -> None:
    global _contador_candidatas_agotadas
    _contador_candidatas_agotadas = 0


@dataclass(slots=True, frozen=True)
class Parada:
    """Una recolección o entrega de un pedido, en coordenadas de grilla (fila, col)."""

    id: str
    tipo: str  # "recogida" | "entrega"
    pos: tuple[int, int]


@dataclass(slots=True)
class Restricciones:
    """Parámetros por pedido que necesita el secuenciador. Todo indexado por `id` de pedido."""

    capacidad: int
    r: dict[str, float] = field(default_factory=dict)          # instante listo (recogida)
    l: dict[str, float | None] = field(default_factory=dict)   # fecha límite de entrega
    theta: dict[str, float | None] = field(default_factory=dict)  # tolerancia de frescura
    carga: dict[str, int] = field(default_factory=dict)        # unidades de capacidad, default 1

    def carga_de(self, pid: str) -> int:
        return self.carga.get(pid, 1)

    def r_de(self, pid: str) -> float:
        return self.r.get(pid, 0.0)

    def l_de(self, pid: str) -> float | None:
        return self.l.get(pid)

    def theta_de(self, pid: str) -> float | None:
        return self.theta.get(pid)


def _mascaras_validas(paradas: list[Parada], restricciones: Restricciones) -> np.ndarray:
    """Precomputa, para cada subconjunto (bitmask), si es precedencia-válido y capacidad-
    válida. Ambas son propiedades monótonas del SUBCONJUNTO (no del orden de visita), así
    que se calculan una sola vez para las 2**n_paradas máscaras."""

    n = len(paradas)
    n_mascaras = 1 << n

    por_id: dict[str, list[int]] = {}
    for idx, parada in enumerate(paradas):
        por_id.setdefault(parada.id, []).append(idx)

    # (pid, idx_recogida o None, idx_entrega). idx_recogida=None significa "ya recogido":
    # el pedido entra a held_karp sólo con su parada de entrega (env.py lo hace así una
    # vez que el vehículo ya pasó por la recogida) -- sin restricción de precedencia, y
    # cuenta como carga ya embarcada desde el inicio de este cálculo.
    pares = []
    for pid, idxs in por_id.items():
        recogidas = [i for i in idxs if paradas[i].tipo == "recogida"]
        entregas = [i for i in idxs if paradas[i].tipo == "entrega"]
        if len(entregas) != 1 or len(recogidas) > 1:
            raise ValueError(f"pedido {pid} debe tener una entrega y a lo más una recogida")
        pares.append((pid, recogidas[0] if recogidas else None, entregas[0]))

    # Vectorizado sobre las 2**n máscaras a la vez (nada de loop por máscara en Python):
    # para cada pedido, qué máscaras "tienen recogida"/"tienen entrega" es una operación de
    # bits sobre todo np.arange(n_mascaras) de una sola vez.
    mascaras = np.arange(n_mascaras, dtype=np.int64)
    ok = np.ones(n_mascaras, dtype=np.bool_)
    carga_actual = np.zeros(n_mascaras, dtype=np.int64)
    for pid, idx_r, idx_e in pares:
        tiene_e = (mascaras & (1 << idx_e)) != 0
        if idx_r is None:
            carga_actual += np.where(~tiene_e, restricciones.carga_de(pid), 0)
            continue
        tiene_r = (mascaras & (1 << idx_r)) != 0
        ok &= ~(tiene_e & ~tiene_r)
        carga_actual += np.where(tiene_r & ~tiene_e, restricciones.carga_de(pid), 0)
    return ok & (carga_actual <= restricciones.capacidad)


def _matriz_estatica(
    paradas: list[Parada], t0: float, pos0: tuple[int, int], travel_fn: TravelFn,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Evalúa travel_fn una sola vez por par de paradas (y desde pos0), en el instante t0,
    y arma matrices NumPy n x n. El DP (numba) y la generación de candidatas por
    perturbación (más abajo) sólo indexan estas matrices — cero llamadas a travel_fn en el
    tramo caliente. Es una foto (snapshot) del tiempo de viaje en t0: sólo se usa para
    ORDENAR y generar candidatas (igual que el resto del pase hacia adelante, nunca decide
    factibilidad); el calendario final siempre se recalcula con el travel_fn real y
    dependiente del tiempo en `verificar_y_calendarizar`."""

    n = len(paradas)
    mat_t = np.zeros((n, n), dtype=np.float64)
    mat_d = np.zeros((n, n), dtype=np.float64)
    dt0 = np.zeros(n, dtype=np.float64)
    dd0 = np.zeros(n, dtype=np.float64)
    for i, parada in enumerate(paradas):
        dt, dm = travel_fn(pos0, parada.pos, t0)
        dt0[i], dd0[i] = dt, dm
        for j, otra in enumerate(paradas):
            if i != j:
                dt, dm = travel_fn(parada.pos, otra.pos, t0)
                mat_t[i, j], mat_d[i, j] = dt, dm
    return mat_t, mat_d, dt0, dd0


@numba.njit(cache=True)
def _dp_numba(
    n: int,
    dt0: np.ndarray,
    dd0: np.ndarray,
    mat_t: np.ndarray,
    mat_d: np.ndarray,
    es_recogida: np.ndarray,
    r: np.ndarray,
    mascaras_ok: np.ndarray,
):
    """Held-Karp clásico (único mejor por (subconjunto, último), no K-beam) sobre las
    matrices ya evaluadas. Tiempos relativos a t0 (t0 se suma afuera). Compilado con numba:
    esto es lo que hace falta para que el pase hacia adelante quepa en el presupuesto de
    tiempo — la misma lógica en Python puro es ~100x más lenta (ver ai/reports/HANDOFF.md)."""

    n_mascaras = 1 << n
    dp_time = np.full((n_mascaras, n), np.inf)
    dp_dist = np.zeros((n_mascaras, n))
    dp_prev = np.full((n_mascaras, n), -1, dtype=np.int32)

    for mascara in range(1, n_mascaras):
        if not mascaras_ok[mascara]:
            continue
        for ultimo in range(n):
            bit = 1 << ultimo
            if (mascara & bit) == 0:
                continue
            prev_mascara = mascara ^ bit
            mejor_t = np.inf
            mejor_d = 0.0
            mejor_prev = -1
            if prev_mascara == 0:
                llegada = dt0[ultimo]
                salida = max(llegada, r[ultimo]) if es_recogida[ultimo] else llegada
                mejor_t = salida
                mejor_d = dd0[ultimo]
            elif mascaras_ok[prev_mascara]:
                for prev_last in range(n):
                    if (prev_mascara & (1 << prev_last)) == 0:
                        continue
                    t_prev = dp_time[prev_mascara, prev_last]
                    if t_prev == np.inf:
                        continue
                    llegada = t_prev + mat_t[prev_last, ultimo]
                    salida = max(llegada, r[ultimo]) if es_recogida[ultimo] else llegada
                    if salida < mejor_t:
                        mejor_t = salida
                        mejor_d = dp_dist[prev_mascara, prev_last] + mat_d[prev_last, ultimo]
                        mejor_prev = prev_last
            dp_time[mascara, ultimo] = mejor_t
            dp_dist[mascara, ultimo] = mejor_d
            dp_prev[mascara, ultimo] = mejor_prev

    return dp_time, dp_dist, dp_prev


def _reconstruir_numba(dp_prev: np.ndarray, n: int, ultimo: int) -> list[int]:
    orden: list[int] = []
    mascara, actual = (1 << n) - 1, ultimo
    while actual != -1:
        orden.append(actual)
        anterior = int(dp_prev[mascara, actual])
        mascara ^= 1 << actual
        actual = anterior
    orden.reverse()
    return orden


def _indices_auxiliares(
    paradas: list[Parada], restricciones: Restricciones,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[int]]:
    """Arrays indexados por posición de parada (no por id de pedido): evita búsquedas en
    dict por cada parada de cada candidata evaluada en `_tiempo_de_orden`, que con ~120
    candidatas por llamada a held_karp era el costo dominante del benchmark (ver HANDOFF)."""

    n = len(paradas)
    es_recogida = np.array([p.tipo == "recogida" for p in paradas], dtype=np.bool_)
    r_idx = np.array(
        [restricciones.r_de(p.id) if p.tipo == "recogida" else 0.0 for p in paradas],
        dtype=np.float64,
    )
    signo = np.where(es_recogida, 1, -1)
    carga_idx = np.array([restricciones.carga_de(p.id) for p in paradas], dtype=np.int64) * signo

    pos_de_id: dict[str, list[int]] = {}
    for idx, p in enumerate(paradas):
        pos_de_id.setdefault(p.id, []).append(idx)
    pareja_idx = [-1] * n
    carga_base = 0
    for idxs in pos_de_id.values():
        if len(idxs) == 2:
            a, b = idxs
            pareja_idx[a], pareja_idx[b] = b, a
        else:
            # Ya recogido (sólo entrega en `paradas`): ya está a bordo desde el inicio.
            (idx_e,) = idxs
            carga_base += restricciones.carga_de(paradas[idx_e].id)

    return es_recogida, r_idx, carga_idx, pareja_idx, carga_base


def _tiempo_de_orden(
    orden: list[int],
    es_recogida: np.ndarray,
    r_idx: np.ndarray,
    carga_idx: np.ndarray,
    pareja_idx: list[int],
    dt0: np.ndarray,
    mat_t: np.ndarray,
    capacidad: int,
    carga_base: int = 0,
) -> float | None:
    """Tiempo total de completado de un orden fijo según la matriz estática (para
    rankear candidatas de perturbación, no para decidir factibilidad). None si viola
    capacidad o precedencia. `carga_base`: pedidos ya recogidos antes de este cálculo
    (sólo tienen parada de entrega en `orden`, pareja_idx=-1: sin precedencia que cumplir)."""

    n = len(orden)
    visitada = [False] * n
    t, carga, anterior = 0.0, carga_base, -1
    for idx in orden:
        if not es_recogida[idx] and pareja_idx[idx] != -1 and not visitada[pareja_idx[idx]]:
            return None
        dt = dt0[idx] if anterior == -1 else mat_t[anterior, idx]
        llegada = t + dt
        t = max(llegada, r_idx[idx]) if es_recogida[idx] else llegada
        carga += carga_idx[idx]
        if carga < 0 or carga > capacidad:
            return None
        visitada[idx] = True
        anterior = idx
    return t


def _candidatas_por_perturbacion(
    orden_base: list[int],
    es_recogida: np.ndarray,
    r_idx: np.ndarray,
    carga_idx: np.ndarray,
    pareja_idx: list[int],
    dt0: np.ndarray,
    mat_t: np.ndarray,
    capacidad: int,
    k: int,
    carga_base: int = 0,
) -> list[list[int]]:
    """K candidatas por tiempo de completado (matriz estática): el óptimo del DP más
    swaps adyacentes y reubicaciones de una parada, filtradas por precedencia/capacidad y
    ordenadas por tiempo. Barato (O(n^2) reordenamientos, cada uno O(n) para puntuar) y en
    la práctica cubre las mismas candidatas relevantes que un beam-DP explícito, sin pagar
    su costo en Python puro."""

    n = len(orden_base)
    vistos = {tuple(orden_base)}
    candidatas = [tuple(orden_base)]

    for i in range(n - 1):
        nuevo = orden_base.copy()
        nuevo[i], nuevo[i + 1] = nuevo[i + 1], nuevo[i]
        t = tuple(nuevo)
        if t not in vistos:
            vistos.add(t)
            candidatas.append(t)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            nuevo = orden_base.copy()
            elem = nuevo.pop(i)
            nuevo.insert(j, elem)
            t = tuple(nuevo)
            if t not in vistos:
                vistos.add(t)
                candidatas.append(t)

    puntuadas = []
    for t in candidatas:
        orden = list(t)
        tiempo = _tiempo_de_orden(
            orden, es_recogida, r_idx, carga_idx, pareja_idx, dt0, mat_t, capacidad, carga_base,
        )
        if tiempo is not None:
            puntuadas.append((tiempo, orden))
    puntuadas.sort(key=lambda par: par[0])
    return [orden for _tiempo, orden in puntuadas[:k]]


def _arrays_calendario(
    paradas: list[Parada], restricciones: Restricciones,
) -> tuple[list[bool], list[float], list[float], list[float], list[int], list[int], int]:
    """Arrays indexados por posición de parada, precomputados UNA vez por llamada a
    `verificar_y_calendarizar` (no por iteración del punto fijo ni por parada visitada):
    evita repetir `restricciones.r_de/l_de/theta_de/carga_de` (dict.get por id de pedido)
    en el tramo caliente, que con miles de calendarizaciones (camino exacto <=4 pedidos, o
    K candidatas del camino heurístico) era costo dominante del benchmark (ver HANDOFF).
    `math.inf` en l/theta significa "sin límite" (evita chequeos `is None` en el loop)."""

    n = len(paradas)
    es_recogida = [p.tipo == "recogida" for p in paradas]
    r_idx = [restricciones.r_de(p.id) if es_recogida[i] else 0.0 for i, p in enumerate(paradas)]
    # ternario explícito (no `or math.inf`): un límite/theta de 0.0 es válido y falsy en Python,
    # `or` lo reemplazaría incorrectamente por "sin límite".
    l_idx = [lim if (lim := restricciones.l_de(p.id)) is not None else math.inf for p in paradas]
    theta_idx = [th if (th := restricciones.theta_de(p.id)) is not None else math.inf for p in paradas]
    carga_idx = [restricciones.carga_de(p.id) for p in paradas]

    pos_de_id: dict[str, list[int]] = {}
    for idx, p in enumerate(paradas):
        pos_de_id.setdefault(p.id, []).append(idx)
    pareja_idx = [-1] * n
    carga_base = 0
    for idxs in pos_de_id.values():
        if len(idxs) == 2:
            a, b = idxs
            pareja_idx[a], pareja_idx[b] = b, a
        else:
            (idx_e,) = idxs
            carga_base += carga_idx[idx_e]

    return es_recogida, r_idx, l_idx, theta_idx, carga_idx, pareja_idx, carga_base


def _simular_adelante(
    orden: list[int],
    paradas: list[Parada],
    t0: float,
    pos0: tuple[int, int],
    travel_fn: TravelFn,
    es_recogida: list[bool],
    r_idx: list[float],
    carga_idx: list[int],
    capacidad: int,
    pins: dict[int, float],
    carga_base: int = 0,
) -> tuple[list[float], list[float], float] | None:
    """Simula hacia adelante el orden fijo dado, honrando cualquier espera estratégica ya
    fijada en `pins` (parada_idx -> instante mínimo de salida). Devuelve (llegadas, salidas,
    distancia_total) o None si se viola capacidad (no debería pasar: ya se podó por
    subconjunto, esto es una verificación barata de más). `carga_base`: pedidos ya
    recogidos antes de este cálculo (sólo aparecen con su parada de entrega en `orden`)."""

    t, pos = t0, pos0
    dist_total = 0.0
    carga = carga_base
    llegadas = [0.0] * len(orden)
    salidas = [0.0] * len(orden)

    for pos_en_orden, idx in enumerate(orden):
        dt, dm = travel_fn(pos, paradas[idx].pos, t)
        llegada = t + dt
        dist_total += dm
        if es_recogida[idx]:
            salida = max(llegada, r_idx[idx])
            if idx in pins:
                salida = max(salida, pins[idx])
            carga += carga_idx[idx]
        else:
            salida = llegada
            carga -= carga_idx[idx]
        if carga < 0 or carga > capacidad:
            return None
        llegadas[pos_en_orden] = llegada
        salidas[pos_en_orden] = salida
        t, pos = salida, paradas[idx].pos

    return llegadas, salidas, dist_total


def _cotas_tardias(
    orden: list[int],
    es_recogida: list[bool],
    l_idx: list[float],
    llegadas: list[float],
    salidas: list[float],
) -> list[float]:
    """Instante más tardío admisible de salida de cada parada, propagado desde la última
    entrega hacia atrás, usando los tramos de viaje reales de la simulación actual."""

    m = len(orden)
    cotas = [math.inf] * m
    for k in range(m - 1, -1, -1):
        idx = orden[k]
        cota = math.inf if es_recogida[idx] else l_idx[idx]
        if k < m - 1:
            tramo = llegadas[k + 1] - salidas[k]
            cota_prev = cotas[k + 1] - tramo
            if cota_prev < cota:
                cota = cota_prev
        cotas[k] = cota
    return cotas


def verificar_y_calendarizar(
    orden: list[int],
    paradas: list[Parada],
    t0: float,
    pos0: tuple[int, int],
    travel_fn: TravelFn,
    restricciones: Restricciones,
    _arrays: tuple | None = None,
    _diagnostico: list[str] | None = None,
) -> tuple[list[float], list[float], float] | None:
    """Punto fijo acotado: en cada iteración simula el orden con las esperas estratégicas
    fijadas hasta ahora, checa fechas límite, y para cada pedido cuya frescura lo exija,
    pospone su recogida lo mínimo necesario (topado por la cota tardía de esa parada). Si
    algo no cabe, o el punto fijo no converge en `_MAX_ITER_PUNTO_FIJO` rondas, es
    infactible.

    Pública (no sólo interna a held_karp): feasibility.py la reutiliza para calcular la
    holgura de frescura restante del plan activo, y los tests la usan para verificar el
    calendario real (con esperas estratégicas incluidas) de una secuencia devuelta.

    `_arrays`: salida de `_arrays_calendario(paradas, restricciones)` ya calculada, para
    quien (como `held_karp`) va a calendarizar MUCHAS órdenes sobre el mismo `paradas` +
    `restricciones` y no quiere repetir ese cómputo por cada una (era costo dominante del
    benchmark con miles de candidatas, ver HANDOFF). Uso normal: se omite y se calcula aquí.

    `_diagnostico`: si se pasa una lista, se le hace `append` del motivo exacto ("capacidad",
    "fecha_limite" o "frescura") cuando se devuelve None -- instrumentación para el
    histograma de motivos de rechazo de feasibility.action_mask, no afecta el resultado."""

    if _arrays is None:
        _arrays = _arrays_calendario(paradas, restricciones)
    es_recogida, r_idx, l_idx, theta_idx, carga_idx, pareja_idx, carga_base = _arrays
    posicion_de_idx = [0] * len(paradas)
    for k, idx in enumerate(orden):
        posicion_de_idx[idx] = k

    pins: dict[int, float] = {}
    # Hueco (T_entrega - S_recogida) que teníamos la última vez que pospusimos ESTE pedido
    # (indexado por parada de RECOGIDA). Si al volver a medirlo no mejoró, posponer más no
    # va a ayudar: significa que el retraso se propaga 1:1 hasta la entrega (no hay espera
    # de preparación aguas abajo que lo absorba), así que el hueco es una CONSTANTE de esta
    # secuencia -- sin esta detección el punto fijo reintenta indefinidamente hasta el tope
    # de iteraciones (visto en el benchmark: siempre agotaba las 20, ver
    # ai/reports/HANDOFF.md).
    gap_previo: dict[int, float] = {}

    for _ in range(_MAX_ITER_PUNTO_FIJO):
        resultado = _simular_adelante(
            orden, paradas, t0, pos0, travel_fn, es_recogida, r_idx, carga_idx,
            restricciones.capacidad, pins, carga_base,
        )
        if resultado is None:
            if _diagnostico is not None:
                _diagnostico.append("capacidad")
            return None
        llegadas, salidas, dist_total = resultado

        for k, idx in enumerate(orden):
            if not es_recogida[idx] and llegadas[k] > l_idx[idx] + _EPS:
                if _diagnostico is not None:
                    _diagnostico.append("fecha_limite")
                return None

        cotas = _cotas_tardias(orden, es_recogida, l_idx, llegadas, salidas)

        cambio = False
        for idx_r, idx_e in enumerate(pareja_idx):
            if not es_recogida[idx_r] or theta_idx[idx_e] == math.inf:
                continue
            theta = theta_idx[idx_e]
            k_r, k_e = posicion_de_idx[idx_r], posicion_de_idx[idx_e]
            gap_actual = llegadas[k_e] - salidas[k_r]

            if gap_actual <= theta + _EPS:
                gap_previo.pop(idx_r, None)
                continue

            if idx_r in gap_previo and gap_actual >= gap_previo[idx_r] - _EPS:
                # posponer no está reduciendo el hueco: no hay forma de cerrarlo
                if _diagnostico is not None:
                    _diagnostico.append("frescura")
                return None

            requerido = llegadas[k_e] - theta
            if requerido > cotas[k_r] + _EPS:
                # no cabe sin romper una fecha límite aguas abajo: el origen es la
                # frescura (exige posponer), lo que lo bloquea es un límite existente.
                if _diagnostico is not None:
                    _diagnostico.append("frescura")
                return None
            gap_previo[idx_r] = gap_actual
            pins[idx_r] = max(pins.get(idx_r, -math.inf), requerido)
            cambio = True

        if not cambio:
            return llegadas, salidas, dist_total

    if _diagnostico is not None:
        _diagnostico.append("frescura")
    return None


def _permutaciones_validas_por_precedencia(paradas: list[Parada]) -> list[list[int]]:
    """Genera DIRECTAMENTE (backtracking) sólo las permutaciones que respetan
    recogida-antes-que-entrega por pedido -- no filtra capacidad todavía, eso lo decide
    `verificar_y_calendarizar` al calendarizar cada una, igual que en el camino heurístico.

    Para n=4 pedidos generar-y-filtrar las 8!=40320 permutaciones con itertools y
    descartar el 94% costaba más que la propia calendarización; construir sólo las 2520
    válidas directamente evita ese desperdicio."""

    n = len(paradas)
    pos_de_id: dict[str, list[int]] = {}
    for idx, p in enumerate(paradas):
        pos_de_id.setdefault(p.id, []).append(idx)
    es_entrega_con_recogida: dict[int, int] = {}  # idx entrega -> idx recogida del mismo pedido
    for idxs in pos_de_id.values():
        if len(idxs) != 2:
            continue  # ya recogido (sólo entrega en `paradas`): sin restricción de precedencia
        a, b = idxs
        r_idx, e_idx = (a, b) if paradas[a].tipo == "recogida" else (b, a)
        es_entrega_con_recogida[e_idx] = r_idx

    resultado: list[list[int]] = []
    actual: list[int] = []
    usado = [False] * n
    recogido = [False] * n

    def backtrack() -> None:
        if len(actual) == n:
            resultado.append(actual.copy())
            return
        for idx in range(n):
            if usado[idx]:
                continue
            recogida_requerida = es_entrega_con_recogida.get(idx)
            if recogida_requerida is not None and not recogido[recogida_requerida]:
                continue
            usado[idx] = True
            actual.append(idx)
            if recogida_requerida is None:
                recogido[idx] = True
            backtrack()
            actual.pop()
            usado[idx] = False
            if recogida_requerida is None:
                recogido[idx] = False

    backtrack()
    return resultado


def held_karp(
    stops, t0, pos0, travel_fn, constraints, k: int = 10,
) -> tuple[list[int] | None, float, float, bool, int]:
    """Devuelve (orden_óptimo, tiempo_total, distancia_total, optimo_exacto, secuencias_evaluadas).
    Si no existe secuencia factible: (None, inf, inf, optimo_exacto, secuencias_evaluadas).

    `stops`: lista de Parada (o dicts con id/tipo/pos), <=12. `constraints`: Restricciones
    (o dict con las mismas claves). `k`: cuántas candidatas por tiempo de completado se
    intentan calendarizar hacia atrás antes de rendirse en el camino heurístico (>4
    pedidos). Parametrizable para el escalón de rendimiento bitmask/beam/K de ai/CLAUDE.md.

    `optimo_exacto`: True si se enumeraron TODAS las secuencias válidas por precedencia
    (<=4 pedidos) y se devuelve la mejor real -- no una aproximación. `secuencias_evaluadas`:
    cuántas se calendarizaron para llegar al resultado. Es parte del contrato con el
    frontend (la UI sólo puede decir "óptimo exacto sobre N secuencias" cuando es cierto):
    no cambiar sin actualizar ai/CLAUDE.md §5.
    """

    global _contador_candidatas_agotadas

    paradas = [p if isinstance(p, Parada) else Parada(**p) for p in stops]
    if len(paradas) > _MAX_PARADAS:
        raise ValueError(f"held_karp soporta hasta {_MAX_PARADAS} paradas, recibió {len(paradas)}")
    restricciones = constraints if isinstance(constraints, Restricciones) else Restricciones(**constraints)

    if not paradas:
        return [], 0.0, 0.0, True, 0

    n = len(paradas)
    n_pedidos = n // 2

    if n_pedidos <= UMBRAL_EXACTO_PEDIDOS:
        t_reloj_inicio = time.perf_counter()
        permutaciones = _permutaciones_validas_por_precedencia(paradas)
        arrays = _arrays_calendario(paradas, restricciones)
        es_recogida, r_idx, _l_idx, _theta_idx, carga_idx, _pareja_idx, carga_base = arrays
        secuencias_evaluadas = len(permutaciones)
        agotado_por_tiempo = False

        # Poda válida (no heurística: preserva la exactitud): el punto fijo sólo puede
        # POSPONER recogidas, así que el tiempo final con espera estratégica de cualquier
        # secuencia es >= su tiempo "naive" (sin esperar a propósito). Una pasada barata
        # (un solo _simular_adelante, sin punto fijo) ordena todo por esa cota inferior;
        # sólo se corre la calendarización completa (cara, con punto fijo) mientras la cota
        # inferior de la candidata siga por debajo de la mejor factible encontrada hasta
        # ahora. Es lo que evita pagar las 2520 verificaciones completas en el caso típico.
        candidatas_naive = []
        for i, perm in enumerate(permutaciones):
            if i % 200 == 0 and time.perf_counter() - t_reloj_inicio > _LIMITE_TIEMPO_EXACTO_S:
                agotado_por_tiempo = True
                break
            resultado = _simular_adelante(
                perm, paradas, t0, pos0, travel_fn, es_recogida, r_idx, carga_idx,
                restricciones.capacidad, {}, carga_base,
            )
            if resultado is not None:
                _llegadas, salidas, _dist = resultado
                candidatas_naive.append((salidas[-1] - t0, perm))
        candidatas_naive.sort(key=lambda c: c[0])

        mejor_orden, mejor_tiempo, mejor_dist = None, math.inf, math.inf
        for i, (cota_inferior, perm) in enumerate(candidatas_naive):
            if cota_inferior >= mejor_tiempo:
                break
            if i % 20 == 0 and time.perf_counter() - t_reloj_inicio > _LIMITE_TIEMPO_EXACTO_S:
                agotado_por_tiempo = True
                break
            resultado = verificar_y_calendarizar(perm, paradas, t0, pos0, travel_fn, restricciones, arrays)
            if resultado is not None:
                _llegadas, salidas, dist_total = resultado
                tiempo_total = salidas[-1] - t0
                if tiempo_total < mejor_tiempo:
                    mejor_orden, mejor_tiempo, mejor_dist = perm, tiempo_total, dist_total

        # optimo_exacto=False en timeout: aunque mejor_orden ya esté verificado (factible de
        # verdad, nunca se devuelve nada sin pasar por verificar_y_calendarizar), no se
        # terminó de comparar contra TODAS las secuencias, así que no hay garantía de que
        # sea la mejor. Nunca se devuelve una secuencia sin verificar por ahorrar tiempo:
        # eso arriesgaría violaciones_frescura, que debe ser 0 siempre.
        optimo_exacto = not agotado_por_tiempo
        if mejor_orden is None:
            _contador_candidatas_agotadas += 1
            return None, math.inf, math.inf, optimo_exacto, secuencias_evaluadas
        return mejor_orden, mejor_tiempo, mejor_dist, optimo_exacto, secuencias_evaluadas

    mascaras_ok = _mascaras_validas(paradas, restricciones)
    mat_t, mat_d, dt0, dd0 = _matriz_estatica(paradas, t0, pos0, travel_fn)
    es_recogida, r_idx, carga_idx, pareja_idx, carga_base = _indices_auxiliares(paradas, restricciones)

    dp_time, _dp_dist, dp_prev = _dp_numba(n, dt0, dd0, mat_t, mat_d, es_recogida, r_idx, mascaras_ok)

    mascara_completa = (1 << n) - 1
    fila_final = dp_time[mascara_completa]
    if np.all(np.isinf(fila_final)):
        candidatas: list[list[int]] = []
    else:
        mejor_ultimo = int(np.argmin(fila_final))
        orden_optimo = _reconstruir_numba(dp_prev, n, mejor_ultimo)
        candidatas = _candidatas_por_perturbacion(
            orden_optimo, es_recogida, r_idx, carga_idx, pareja_idx, dt0, mat_t,
            restricciones.capacidad, k, carga_base,
        )

    arrays = _arrays_calendario(paradas, restricciones)
    evaluadas = 0
    for orden in candidatas:
        evaluadas += 1
        resultado = verificar_y_calendarizar(orden, paradas, t0, pos0, travel_fn, restricciones, arrays)
        if resultado is not None:
            _llegadas, salidas, dist_total = resultado
            tiempo_total = salidas[-1] - t0
            return orden, tiempo_total, dist_total, False, evaluadas

    _contador_candidatas_agotadas += 1
    return None, math.inf, math.inf, False, evaluadas
