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
from dataclasses import dataclass, field
from typing import Callable

import numba
import numpy as np

TravelFn = Callable[[tuple[int, int], tuple[int, int], float], tuple[float, float]]

_MAX_PARADAS = 12
_MAX_ITER_PUNTO_FIJO = 20
_EPS = 1e-6

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

    pares = []
    for pid, idxs in por_id.items():
        recogidas = [i for i in idxs if paradas[i].tipo == "recogida"]
        entregas = [i for i in idxs if paradas[i].tipo == "entrega"]
        if len(recogidas) != 1 or len(entregas) != 1:
            raise ValueError(f"pedido {pid} debe tener exactamente una recogida y una entrega")
        pares.append((pid, recogidas[0], entregas[0]))

    # Vectorizado sobre las 2**n máscaras a la vez (nada de loop por máscara en Python):
    # para cada pedido, qué máscaras "tienen recogida"/"tienen entrega" es una operación de
    # bits sobre todo np.arange(n_mascaras) de una sola vez.
    mascaras = np.arange(n_mascaras, dtype=np.int64)
    ok = np.ones(n_mascaras, dtype=np.bool_)
    carga_actual = np.zeros(n_mascaras, dtype=np.int64)
    for pid, idx_r, idx_e in pares:
        tiene_r = (mascaras & (1 << idx_r)) != 0
        tiene_e = (mascaras & (1 << idx_e)) != 0
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
    for idxs in pos_de_id.values():
        a, b = idxs
        pareja_idx[a], pareja_idx[b] = b, a

    return es_recogida, r_idx, carga_idx, pareja_idx


def _tiempo_de_orden(
    orden: list[int],
    es_recogida: np.ndarray,
    r_idx: np.ndarray,
    carga_idx: np.ndarray,
    pareja_idx: list[int],
    dt0: np.ndarray,
    mat_t: np.ndarray,
    capacidad: int,
) -> float | None:
    """Tiempo total de completado de un orden fijo según la matriz estática (para
    rankear candidatas de perturbación, no para decidir factibilidad). None si viola
    capacidad o precedencia."""

    n = len(orden)
    visitada = [False] * n
    t, carga, anterior = 0.0, 0, -1
    for idx in orden:
        if not es_recogida[idx] and not visitada[pareja_idx[idx]]:
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
        tiempo = _tiempo_de_orden(orden, es_recogida, r_idx, carga_idx, pareja_idx, dt0, mat_t, capacidad)
        if tiempo is not None:
            puntuadas.append((tiempo, orden))
    puntuadas.sort(key=lambda par: par[0])
    return [orden for _tiempo, orden in puntuadas[:k]]


def _simular_adelante(
    orden: list[int],
    paradas: list[Parada],
    t0: float,
    pos0: tuple[int, int],
    travel_fn: TravelFn,
    restricciones: Restricciones,
    pins: dict[int, float],
) -> tuple[list[float], list[float], float] | None:
    """Simula hacia adelante el orden fijo dado, honrando cualquier espera estratégica ya
    fijada en `pins` (parada_idx -> instante mínimo de salida). Devuelve (llegadas, salidas,
    distancia_total) o None si se viola capacidad (no debería pasar: ya se podó por
    subconjunto, esto es una verificación barata de más)."""

    t, pos = t0, pos0
    dist_total = 0.0
    carga = 0
    llegadas = [0.0] * len(orden)
    salidas = [0.0] * len(orden)

    for pos_en_orden, idx in enumerate(orden):
        parada = paradas[idx]
        dt, dm = travel_fn(pos, parada.pos, t)
        llegada = t + dt
        dist_total += dm
        if parada.tipo == "recogida":
            salida = max(llegada, restricciones.r_de(parada.id))
            if idx in pins:
                salida = max(salida, pins[idx])
            carga += restricciones.carga_de(parada.id)
        else:
            salida = llegada
            carga -= restricciones.carga_de(parada.id)
        if carga < 0 or carga > restricciones.capacidad:
            return None
        llegadas[pos_en_orden] = llegada
        salidas[pos_en_orden] = salida
        t, pos = salida, parada.pos

    return llegadas, salidas, dist_total


def _cotas_tardias(
    orden: list[int],
    paradas: list[Parada],
    restricciones: Restricciones,
    llegadas: list[float],
    salidas: list[float],
) -> list[float]:
    """Instante más tardío admisible de salida de cada parada, propagado desde la última
    entrega hacia atrás, usando los tramos de viaje reales de la simulación actual."""

    m = len(orden)
    cotas = [math.inf] * m
    for k in range(m - 1, -1, -1):
        parada = paradas[orden[k]]
        cota = math.inf
        if parada.tipo == "entrega":
            l = restricciones.l_de(parada.id)
            if l is not None:
                cota = l
        if k < m - 1:
            tramo = llegadas[k + 1] - salidas[k]
            cota = min(cota, cotas[k + 1] - tramo)
        cotas[k] = cota
    return cotas


def verificar_y_calendarizar(
    orden: list[int],
    paradas: list[Parada],
    t0: float,
    pos0: tuple[int, int],
    travel_fn: TravelFn,
    restricciones: Restricciones,
) -> tuple[list[float], list[float], float] | None:
    """Punto fijo acotado: en cada iteración simula el orden con las esperas estratégicas
    fijadas hasta ahora, checa fechas límite, y para cada pedido cuya frescura lo exija,
    pospone su recogida lo mínimo necesario (topado por la cota tardía de esa parada). Si
    algo no cabe, o el punto fijo no converge en `_MAX_ITER_PUNTO_FIJO` rondas, es
    infactible.

    Pública (no sólo interna a held_karp): feasibility.py la reutiliza para calcular la
    holgura de frescura restante del plan activo, y los tests la usan para verificar el
    calendario real (con esperas estratégicas incluidas) de una secuencia devuelta."""

    pos_de_recogida: dict[str, int] = {}
    pos_de_entrega: dict[str, int] = {}
    for idx_en_orden, idx in enumerate(orden):
        parada = paradas[idx]
        if parada.tipo == "recogida":
            pos_de_recogida[parada.id] = idx
        else:
            pos_de_entrega[parada.id] = idx

    pins: dict[int, float] = {}
    # Hueco (T_entrega - S_recogida) que teníamos la última vez que pospusimos ESTE pedido.
    # Si al volver a medirlo no mejoró, posponer más no va a ayudar: significa que el
    # retraso se propaga 1:1 hasta la entrega (no hay espera de preparación aguas abajo que
    # lo absorba), así que el hueco es una CONSTANTE de esta secuencia -- sin esta detección
    # el punto fijo reintenta indefinidamente hasta el tope de iteraciones (visto en el
    # benchmark: siempre agotaba las 20, ver ai/reports/HANDOFF.md).
    gap_previo: dict[str, float] = {}

    for _ in range(_MAX_ITER_PUNTO_FIJO):
        resultado = _simular_adelante(orden, paradas, t0, pos0, travel_fn, restricciones, pins)
        if resultado is None:
            return None
        llegadas, salidas, dist_total = resultado

        posicion_de_idx = {idx: k for k, idx in enumerate(orden)}

        for k, idx in enumerate(orden):
            parada = paradas[idx]
            if parada.tipo == "entrega":
                l = restricciones.l_de(parada.id)
                if l is not None and llegadas[k] > l + _EPS:
                    return None

        cotas = _cotas_tardias(orden, paradas, restricciones, llegadas, salidas)

        cambio = False
        for pid, idx_e in pos_de_entrega.items():
            theta = restricciones.theta_de(pid)
            if theta is None:
                continue
            idx_r = pos_de_recogida[pid]
            k_r, k_e = posicion_de_idx[idx_r], posicion_de_idx[idx_e]
            gap_actual = llegadas[k_e] - salidas[k_r]

            if gap_actual <= theta + _EPS:
                gap_previo.pop(pid, None)
                continue

            if pid in gap_previo and gap_actual >= gap_previo[pid] - _EPS:
                return None  # posponer no está reduciendo el hueco: no hay forma de cerrarlo

            requerido = llegadas[k_e] - theta
            if requerido > cotas[k_r] + _EPS:
                return None  # no cabe sin romper una fecha límite aguas abajo
            gap_previo[pid] = gap_actual
            pins[idx_r] = max(pins.get(idx_r, -math.inf), requerido)
            cambio = True

        if not cambio:
            return llegadas, salidas, dist_total

    return None


def held_karp(
    stops, t0, pos0, travel_fn, constraints, k: int = 10,
) -> tuple[list[int] | None, float, float]:
    """Devuelve (orden_óptimo, tiempo_total, distancia_total).
    Si no existe secuencia factible devuelve (None, inf, inf).

    `stops`: lista de Parada (o dicts con id/tipo/pos), <=12. `constraints`: Restricciones
    (o dict con las mismas claves). `k`: cuántas candidatas por tiempo de completado se
    intentan calendarizar hacia atrás antes de rendirse (ver módulo, arquitectura de 4
    pasos). Parametrizable para el escalón de rendimiento bitmask/beam/K de ai/CLAUDE.md.
    """

    global _contador_candidatas_agotadas

    paradas = [p if isinstance(p, Parada) else Parada(**p) for p in stops]
    if len(paradas) > _MAX_PARADAS:
        raise ValueError(f"held_karp soporta hasta {_MAX_PARADAS} paradas, recibió {len(paradas)}")
    restricciones = constraints if isinstance(constraints, Restricciones) else Restricciones(**constraints)

    if not paradas:
        return [], 0.0, 0.0

    n = len(paradas)
    mascaras_ok = _mascaras_validas(paradas, restricciones)
    mat_t, mat_d, dt0, dd0 = _matriz_estatica(paradas, t0, pos0, travel_fn)
    es_recogida, r_idx, carga_idx, pareja_idx = _indices_auxiliares(paradas, restricciones)

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
            restricciones.capacidad, k,
        )

    for orden in candidatas:
        resultado = verificar_y_calendarizar(orden, paradas, t0, pos0, travel_fn, restricciones)
        if resultado is not None:
            _llegadas, salidas, dist_total = resultado
            tiempo_total = salidas[-1] - t0
            return orden, tiempo_total, dist_total

    _contador_candidatas_agotadas += 1
    return None, math.inf, math.inf
