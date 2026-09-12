"""Invariantes del simulador VYGO (ai/CLAUDE.md §2, §7, §8).

El entorno (vygo.env, vygo.geo, vygo.sequencer, ...) todavía no está implementado, así que
las seis pruebas se marcan `xfail`: documentan el contrato que el simulador deberá cumplir
en cuanto exista. Quitar el xfail (o volverlo strict=True) en cuanto la implementación real
esté lista — mientras tanto un xpass inesperado no rompe la corrida (strict=False).
"""

from __future__ import annotations

import itertools

import pytest

pytestmark = pytest.mark.xfail(
    reason="entorno de simulación aún no implementado (ver ai/CLAUDE.md §4)",
    strict=False,
)


def test_conservacion_pedidos():
    """Todo pedido generado termina en exactamente uno de los estados terminales."""
    from vygo.env import VygoEnv

    env = VygoEnv()
    obs, info = env.reset(seed=0)
    terminado = False
    while not terminado:
        accion = env.action_space.sample()
        obs, reward, terminado, truncado, info = env.step(accion)
        terminado = terminado or truncado

    generados = info["pedidos_generados"]
    resueltos = (
        info["pedidos_entregados"]
        + info["pedidos_rechazados"]
        + info["pedidos_expirados"]
        + info["pedidos_perdidos"]
        + info["pedidos_cancelados"]
    )
    assert generados == resueltos


def test_carga_en_rango_capacidad():
    """La carga a bordo nunca excede Q ni baja de 0 durante el episodio."""
    from vygo.env import VygoEnv

    env = VygoEnv()
    obs, info = env.reset(seed=0)
    terminado = False
    while not terminado:
        accion = env.action_space.sample()
        obs, reward, terminado, truncado, info = env.step(accion)
        terminado = terminado or truncado
        assert 0 <= info["carga_actual"] <= info["capacidad_q"]


def test_violaciones_frescura_cero():
    """violaciones_frescura debe ser 0 SIEMPRE (ai/CLAUDE.md §2.2): si no, es un bug de la
    máscara de factibilidad, no un problema de entrenamiento."""
    from vygo.env import VygoEnv

    env = VygoEnv()
    obs, info = env.reset(seed=0)
    terminado = False
    while not terminado:
        accion = env.action_space.sample()
        obs, reward, terminado, truncado, info = env.step(accion)
        terminado = terminado or truncado
        assert info["violaciones_frescura"] == 0


def test_contabilidad_ingresos_costos():
    """La recompensa acumulada del episodio coincide con tarifas+propinas menos costos y
    penalizaciones (ai/CLAUDE.md §7)."""
    from vygo.env import VygoEnv

    env = VygoEnv()
    obs, info = env.reset(seed=0)
    recompensa_acumulada = 0.0
    terminado = False
    while not terminado:
        accion = env.action_space.sample()
        obs, reward, terminado, truncado, info = env.step(accion)
        terminado = terminado or truncado
        recompensa_acumulada += reward

    ledger = info["ledger"]
    esperado = (
        ledger["ingreso"] - ledger["costo_distancia"] - ledger["penalizaciones"] - ledger["costo_tiempo"]
    )
    assert recompensa_acumulada == pytest.approx(esperado)


def test_monotonia_fifo():
    """Salir más tarde de un nodo nunca hace que se llegue antes al siguiente (consistencia
    FIFO de la función de tiempo de viaje, docs/modelo-matematico.md §3.1)."""
    from vygo.geo import tiempo_viaje

    origen = (25.6866, -100.3161)
    destino = (25.6714, -100.3089)

    t_temprano = tiempo_viaje(origen, destino, t_salida=0.0)
    t_tarde = tiempo_viaje(origen, destino, t_salida=600.0)

    assert (600.0 + t_tarde) >= (0.0 + t_temprano)


def test_held_karp_vs_fuerza_bruta_3_pedidos():
    """Held-Karp debe encontrar el mismo óptimo que enumerar las 6 secuencias posibles con
    3 pedidos (<=12 paradas, ai/CLAUDE.md §2.1)."""
    from vygo.sequencer import held_karp

    stops = [
        {"id": "o1", "pos": (25.68, -100.31)},
        {"id": "o2", "pos": (25.69, -100.32)},
        {"id": "o3", "pos": (25.70, -100.30)},
    ]
    pos0 = (25.67, -100.33)

    def travel_fn(a, b):
        ax, ay = a
        bx, by = b
        return (abs(ax - bx) + abs(ay - by)) * 1000.0

    orden_hk, tiempo_hk, _ = held_karp(
        stops, t0=0.0, pos0=pos0, travel_fn=travel_fn, constraints=None,
    )

    mejor_tiempo = min(
        sum(
            travel_fn(pos0 if i == 0 else stops[perm[i - 1]]["pos"], stops[perm[i]]["pos"])
            for i in range(len(perm))
        )
        for perm in itertools.permutations(range(len(stops)))
    )

    assert tiempo_hk == pytest.approx(mejor_tiempo)
