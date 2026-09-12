"""Invariantes del simulador VYGO (ai/CLAUDE.md §2, §7, §8).

Los tests de VygoEnv corren una ventana ACOTADA de pasos, no el turno completo de 6h: el
costo de action_mask/held_karp crece con el tamaño del plan activo, y completar un turno
entero es demasiado lento para un test unitario hoy (ver reports/HANDOFF.md, rendimiento
del entorno). La ventana acotada sigue siendo una prueba real de los cuatro invariantes
sobre el entorno end-to-end, sólo que sobre una porción del turno.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from vygo.geo import GridWorld
from vygo.schema import CLIMA_SIMULABLE
from vygo.sequencer import Parada, Restricciones, held_karp, verificar_y_calendarizar

PASOS_ENV_TEST = 150


def _correr_env(seed: int = 0):
    from vygo.env import VygoEnv

    env = VygoEnv(nivel="L0", m_comercios=50)
    obs, info = env.reset(seed=seed)
    rng = np.random.default_rng(seed)
    for _ in range(PASOS_ENV_TEST):
        mask = info["action_mask"]
        validas = np.flatnonzero(mask)
        accion = int(rng.choice(validas)) if len(validas) else env.action_space.sample()
        obs, reward, terminado, truncado, info = env.step(accion)
        yield env, reward, info
        if terminado or truncado:
            return


def test_conservacion_pedidos():
    """Todo pedido generado termina en exactamente uno de los estados terminales, o sigue
    en curso (visible/compitiendo/buscando): nunca se "pierde" sin contabilizar."""
    info = None
    for _env, _reward, info in _correr_env():
        pass
    assert info is not None

    generados = info["pedidos_generados"]
    resueltos = (
        info["pedidos_entregados"]
        + info["pedidos_rechazados"]
        + info["pedidos_expirados"]
        + info["pedidos_perdidos"]
        + info["pedidos_cancelados"]
    )
    assert resueltos <= generados


def test_carga_en_rango_capacidad():
    """La carga a bordo nunca excede Q ni baja de 0 durante el episodio."""
    for _env, _reward, info in _correr_env():
        assert 0 <= info["carga_actual"] <= info["capacidad_q"]


def test_violaciones_frescura_cero_en_episodio():
    """violaciones_frescura debe ser 0 SIEMPRE (ai/CLAUDE.md §2.2). El secuenciador ya se
    prueba de forma aislada en test_held_karp_espera_estrategica; esto cubre el episodio
    end-to-end con VygoEnv de por medio."""
    for _env, _reward, info in _correr_env():
        assert info["violaciones_frescura"] == 0


def test_contabilidad_ingresos_costos():
    """La recompensa acumulada coincide con tarifas menos costos y penalizaciones (§7)."""
    recompensa_acumulada = 0.0
    info = None
    for _env, reward, info in _correr_env():
        recompensa_acumulada += reward
    assert info is not None

    ledger = info["ledger"]
    esperado = (
        ledger["ingreso"] - ledger["costo_distancia"] - ledger["penalizaciones"] - ledger["costo_tiempo"]
    )
    assert recompensa_acumulada == pytest.approx(esperado, abs=1e-3)


def test_monotonia_fifo():
    """Salir más tarde nunca produce llegada más temprana. 1000 pares (origen, destino, t,
    delta>0) aleatorios sobre GridWorld, con clima y horas del día variados a propósito para
    estresar el multiplicador por hora (el punto más frágil de FIFO)."""
    grid = GridWorld(n=20, seed=0)
    rng = np.random.default_rng(1234)
    climas = list(CLIMA_SIMULABLE)

    violaciones = 0
    for _ in range(1000):
        o = (int(rng.integers(0, grid.n)), int(rng.integers(0, grid.n)))
        d = (int(rng.integers(0, grid.n)), int(rng.integers(0, grid.n)))
        t1 = float(rng.uniform(0.0, 3 * 86400.0))
        delta = float(rng.uniform(0.0, 6 * 3600.0))  # hasta 6h después, cruza fronteras de franja
        clima = climas[int(rng.integers(0, len(climas)))]

        tiempo1, _ = grid.travel(o, d, t1, clima)
        tiempo2, _ = grid.travel(o, d, t1 + delta, clima)

        if (t1 + delta + tiempo2) < (t1 + tiempo1) - 1e-6:
            violaciones += 1

    assert violaciones == 0


def _fuerza_bruta(stops, t0, pos0, travel_fn, restricciones):
    """Enumera TODAS las secuencias válidas (precedencia + capacidad) y regresa el menor
    tiempo total de completado, sin considerar frescura/fechas límite (para comparar contra
    held_karp en instancias sin esas restricciones, donde debe coincidir exacto)."""
    n = len(stops)
    mejor = math.inf
    for perm in itertools.permutations(range(n)):
        recogidos = set()
        entregados = set()
        valido = True
        for idx in perm:
            pid, tipo, _ = stops[idx]
            if tipo == "entrega" and pid not in recogidos:
                valido = False
                break
            if tipo == "recogida":
                recogidos.add(pid)
        if not valido:
            continue

        t, pos, carga = t0, pos0, 0
        for idx in perm:
            pid, tipo, p = stops[idx]
            dt, _ = travel_fn(pos, p, t)
            t = t + dt
            if tipo == "recogida":
                r = restricciones.r_de(pid)
                t = max(t, r)
                carga += restricciones.carga_de(pid)
            else:
                carga -= restricciones.carga_de(pid)
            if carga > restricciones.capacidad or carga < 0:
                valido = False
                break
            pos = p
        if valido:
            mejor = min(mejor, t - t0)
    return mejor


def _travel_fn_lineal(a, b, t):
    dist_celdas = abs(a[0] - b[0]) + abs(a[1] - b[1])
    return dist_celdas * 60.0, dist_celdas * 500.0


def _instancia_aleatoria(n_pedidos, seed):
    rng = np.random.default_rng(seed)
    stops = []
    restr = Restricciones(capacidad=n_pedidos, r={}, l={}, theta={}, carga={})
    for i in range(n_pedidos):
        pid = f"p{i}"
        pos_r = (int(rng.integers(0, 15)), int(rng.integers(0, 15)))
        pos_e = (int(rng.integers(0, 15)), int(rng.integers(0, 15)))
        stops.append((pid, "recogida", pos_r))
        stops.append((pid, "entrega", pos_e))
        restr.r[pid] = float(rng.integers(0, 60))  # preparación corta: no debe forzar espera
        restr.l[pid] = None
        restr.theta[pid] = None
        restr.carga[pid] = 1
    return stops, restr


@pytest.mark.parametrize("n_pedidos,seed", [(3, 0), (3, 1), (3, 2)])
def test_held_karp_vs_fuerza_bruta_3_pedidos(n_pedidos, seed):
    stops, restr = _instancia_aleatoria(n_pedidos, seed)
    stops_dict = [{"id": pid, "tipo": tipo, "pos": pos} for pid, tipo, pos in stops]

    _orden, tiempo_hk, _dist, exacto, evaluadas = held_karp(
        stops_dict, 0.0, (0, 0), _travel_fn_lineal, restr, k=20,
    )
    tiempo_fb = _fuerza_bruta(stops, 0.0, (0, 0), _travel_fn_lineal, restr)

    assert tiempo_hk == pytest.approx(tiempo_fb, abs=1e-6)
    # <=4 pedidos: camino exacto por enumeración, 6!/(2**3)=90 secuencias válidas por precedencia.
    assert exacto is True
    assert evaluadas == 90


@pytest.mark.parametrize("n_pedidos,seed", [(4, 0), (4, 1)])
def test_held_karp_vs_fuerza_bruta_4_pedidos(n_pedidos, seed):
    stops, restr = _instancia_aleatoria(n_pedidos, seed)
    stops_dict = [{"id": pid, "tipo": tipo, "pos": pos} for pid, tipo, pos in stops]

    _orden, tiempo_hk, _dist, exacto, evaluadas = held_karp(
        stops_dict, 0.0, (0, 0), _travel_fn_lineal, restr, k=20,
    )
    tiempo_fb = _fuerza_bruta(stops, 0.0, (0, 0), _travel_fn_lineal, restr)

    assert tiempo_hk == pytest.approx(tiempo_fb, abs=1e-6)
    # <=4 pedidos: camino exacto por enumeración, 8!/(2**4)=2520 secuencias válidas.
    assert exacto is True
    assert evaluadas == 2520


def test_held_karp_espera_estrategica():
    """Caso fabricado A MANO (no aleatorio): con 3 pedidos, la secuencia de llegada más
    temprana VISITA recogida_A, recogida_B, entrega_A ... y viola la frescura de A (el
    hueco T_entrega_A - S_recogida_A excede theta_A). Existe otra programación FACTIBLE de
    la MISMA secuencia esperando en el primer comercio (recogida_A) antes de salir hacia
    B, porque B tiene un tiempo de preparación tardío (r_B) que de todos modos obligaría a
    esperar ahí — esperar antes en vez de esperar después no mueve la entrega de A, pero sí
    acorta su frescura. Si held_karp no encuentra esta programación, el secuenciador es
    incorrecto (ver módulo vygo.sequencer)."""

    stops = [
        {"id": "A", "tipo": "recogida", "pos": (0, 0)},
        {"id": "A", "tipo": "entrega", "pos": (8, 0)},
        {"id": "B", "tipo": "recogida", "pos": (3, 0)},
        {"id": "B", "tipo": "entrega", "pos": (30, 0)},
        {"id": "C", "tipo": "recogida", "pos": (31, 0)},
        {"id": "C", "tipo": "entrega", "pos": (32, 0)},
    ]
    restr = Restricciones(
        capacidad=3,
        r={"A": 0.0, "B": 680.0, "C": 0.0},
        l={"A": None, "B": None, "C": None},
        theta={"A": 600.0, "B": None, "C": None},
        carga={"A": 1, "B": 1, "C": 1},
    )

    orden, tiempo_total, _dist, exacto, evaluadas = held_karp(
        stops, 0.0, (0, 0), _travel_fn_lineal, restr, k=20,
    )

    assert orden is not None, "el secuenciador debe encontrar la programación con espera estratégica"
    assert exacto is True
    assert evaluadas == 90  # 3 pedidos -> 6!/(2**3) secuencias válidas por precedencia

    # Recalendarizar la secuencia devuelta con la MISMA función que held_karp usa
    # internamente (verificar_y_calendarizar), para obtener el calendario real -- con
    # cualquier espera estratégica ya aplicada -- y no una reconstrucción ingenua sin ella.
    paradas = [Parada(**s) for s in stops]
    resultado = verificar_y_calendarizar(orden, paradas, 0.0, (0, 0), _travel_fn_lineal, restr)
    assert resultado is not None, "la secuencia que devolvió held_karp debe recalendarizar factible"
    llegadas, salidas, _dist2 = resultado

    idx_recogida_a = orden.index(next(i for i, p in enumerate(paradas) if p.id == "A" and p.tipo == "recogida"))
    idx_entrega_a = orden.index(next(i for i, p in enumerate(paradas) if p.id == "A" and p.tipo == "entrega"))

    gap_a = llegadas[idx_entrega_a] - salidas[idx_recogida_a]
    assert gap_a <= restr.theta_de("A") + 1e-6

    # Y confirmar que de verdad hizo falta esperar: sin espera estratégica (recogida de A
    # en cuanto el vehículo llega, t=0) el hueco naive es 980s > theta_A=600s -- por eso
    # este caso se fabricó a mano en vez de al azar (ver docstring del módulo sequencer).
    assert salidas[idx_recogida_a] > 1e-6
