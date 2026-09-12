"""Benchmarks del núcleo determinista (sequencer.held_karp, feasibility.action_mask).

Uso: python -m vygo.bench
Objetivos (ai/CLAUDE.md, tarea del núcleo determinista):
  - held_karp con 8 paradas (K_A=4 pedidos, el caso real de uso -- el benchmark de 12
    paradas/K=20 candidatas ya se optimizó en el bloque anterior y no se vuelve a tocar
    aquí): p95 < 2 ms sobre 200 instancias aleatorias.
  - action_mask con 8 ofertas y 4 pedidos activos (K_A=4): p95 < 15 ms.
"""

from __future__ import annotations

import time

import numpy as np

from vygo.feasibility import action_mask
from vygo.insertion import EstadoRuta, OfertaCandidata
from vygo.schema import Clima
from vygo.sequencer import Parada, Restricciones, candidatas_agotadas, held_karp, reset_candidatas_agotadas


def _travel_fn(a: tuple[int, int], b: tuple[int, int], _t: float) -> tuple[float, float]:
    d = abs(a[0] - b[0]) + abs(a[1] - b[1])
    return d * 60.0, d * 500.0


def _instancia_held_karp(n_pedidos: int, seed: int):
    """Instancia aleatoria PERO representativa: paradas en un radio local de reparto (no
    esparcidas por los 20x20 de toda la rejilla -- un plan activo real es geográficamente
    cercano) y holguras de frescura generosas frente a esa distancia típica. Con la primera
    versión (posiciones 0-20, theta 600-3600s) la mayoría de las instancias eran
    genuinamente infactibles por construcción del benchmark, no por el secuenciador -- eso
    inflaba artificialmente candidatas_agotadas y el tiempo medido (ver HANDOFF)."""
    rng = np.random.default_rng(seed)
    stops = []
    restr = Restricciones(capacidad=n_pedidos, r={}, l={}, theta={}, carga={})
    for i in range(n_pedidos):
        pid = f"p{i}"
        stops.append({"id": pid, "tipo": "recogida", "pos": (int(rng.integers(0, 8)), int(rng.integers(0, 8)))})
        stops.append({"id": pid, "tipo": "entrega", "pos": (int(rng.integers(0, 8)), int(rng.integers(0, 8)))})
        restr.r[pid] = float(rng.integers(0, 180))
        restr.l[pid] = None
        restr.theta[pid] = float(rng.integers(900, 3600))
        restr.carga[pid] = 1
    return stops, restr


def bench_held_karp(n_instancias: int = 200, n_paradas: int = 8, k: int = 10):
    n_pedidos = n_paradas // 2
    tiempos = np.empty(n_instancias)
    exactos = 0
    reset_candidatas_agotadas()

    # Calentamiento: la primera llamada a held_karp paga la compilación JIT de numba
    # (~1-2s); no debe contaminar el benchmark, igual que nadie mide en frío un servicio.
    # Con <=4 pedidos el camino es puro Python (enumeración exacta, sin numba) pero el
    # calentamiento no hace daño y mantiene el benchmark uniforme para cualquier n_paradas.
    stops_calentar, restr_calentar = _instancia_held_karp(n_pedidos, 999999)
    held_karp(stops_calentar, 0.0, (0, 0), _travel_fn, restr_calentar, k=k)
    reset_candidatas_agotadas()

    for seed in range(n_instancias):
        stops, restr = _instancia_held_karp(n_pedidos, seed)
        t0 = time.perf_counter()
        _orden, _tiempo, _dist, exacto, _evaluadas = held_karp(
            stops, 0.0, (0, 0), _travel_fn, restr, k=k,
        )
        tiempos[seed] = time.perf_counter() - t0
        exactos += int(exacto)
    return tiempos, candidatas_agotadas(), exactos


def _estado_benchmark(seed: int) -> EstadoRuta:
    """Plan activo con K_A=4 pedidos (8 paradas, el caso real de uso) más 8 ofertas
    candidatas, todo en el mismo radio local de reparto que `_instancia_held_karp`."""
    rng = np.random.default_rng(seed)
    plan, restr = [], Restricciones(capacidad=4, r={}, l={}, theta={}, carga={})
    for i in range(4):
        pid = f"plan{i}"
        plan.append(Parada(pid, "recogida", (int(rng.integers(0, 8)), int(rng.integers(0, 8)))))
        plan.append(Parada(pid, "entrega", (int(rng.integers(0, 8)), int(rng.integers(0, 8)))))
        restr.r[pid] = 0.0
        restr.l[pid] = None
        restr.theta[pid] = float(rng.integers(900, 3600))
        restr.carga[pid] = 1

    ofertas = []
    for i in range(8):
        ofertas.append(OfertaCandidata(
            id=f"of{i}",
            pos_recogida=(int(rng.integers(0, 8)), int(rng.integers(0, 8))),
            pos_entrega=(int(rng.integers(0, 8)), int(rng.integers(0, 8))),
            r=0.0, l=None, theta=float(rng.integers(900, 3600)), carga=1,
            expira_en=float(rng.integers(60, 600)),
        ))

    return EstadoRuta(
        t=0.0, pos=(0, 0), clima=Clima.DESPEJADO, plan=plan, restricciones=restr,
        travel_fn=_travel_fn, ofertas=ofertas,
    )


def bench_action_mask(n_instancias: int = 200):
    tiempos = np.empty(n_instancias)
    for seed in range(n_instancias):
        estado = _estado_benchmark(seed)
        t0 = time.perf_counter()
        action_mask(estado)
        tiempos[seed] = time.perf_counter() - t0
    return tiempos


def _reportar(nombre: str, tiempos: np.ndarray, objetivo_ms: float) -> float:
    p50, p95, p99 = np.percentile(tiempos, [50, 95, 99]) * 1000.0
    estado = "OK" if p95 < objetivo_ms else "FUERA DE OBJETIVO"
    print(f"{nombre}: p50={p50:.3f}ms p95={p95:.3f}ms p99={p99:.3f}ms (objetivo p95<{objetivo_ms}ms) [{estado}]")
    return p95


if __name__ == "__main__":
    n_instancias = 200
    tiempos_hk, agotadas, exactos = bench_held_karp(n_instancias=n_instancias)
    _reportar(f"held_karp (8 paradas / K_A=4, {n_instancias} instancias)", tiempos_hk, 2.0)
    print(f"  candidatas_agotadas: {agotadas}/{n_instancias}  optimo_exacto: {exactos}/{n_instancias}")

    tiempos_am = bench_action_mask(n_instancias=n_instancias)
    _reportar(f"action_mask (8 ofertas, 4 pedidos activos, {n_instancias} instancias)", tiempos_am, 15.0)
