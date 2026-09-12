# HANDOFF — B1-nucleo-determinista

_Generado: 2026-09-12T10:25:34+00:00 · commit `309902b` (sucio: hay cambios sin commitear)_

## Qué se construyó

Núcleo determinista del secuenciador (sobre el andamiaje de B0: schema.py, run.py, report.py, ya existentes):

- `vygo/geo.py`: `GridWorld` (rejilla NxN, distancia Manhattan, matriz de distancias/tiempo-base precalculada). Multiplicador de hora INTERPOLADO linealmente entre anclas (no escalón discreto) a propósito: un escalón puede violar FIFO sin importar qué tan chico sea el instante de corte; la interpolación lo evita por construcción.
- `vygo/sequencer.py`: `held_karp` con la arquitectura de 4 pasos obligatoria — DP hacia adelante (single-best, JIT con numba) para podar por capacidad/precedencia y generar el orden óptimo por tiempo estático, `_candidatas_por_perturbacion` genera K variantes cercanas (swaps/reubicaciones) para diversidad, y `verificar_y_calendarizar` hace el pase hacia atrás con punto fijo acotado que calcula la ESPERA ESTRATÉGICA en cada recogida (nunca se decide frescura en el pase hacia adelante).
- `vygo/insertion.py`: `eval_insertion`, cachea `held_karp(plan)` en `EstadoRuta` para no repetirlo por cada oferta evaluada.
- `vygo/feasibility.py`: `action_mask`, incluye el bloqueo de `reposicionarse` por holgura de frescura < 5 min.
- `vygo/bench.py`: benchmarks reproducibles de `held_karp` y `action_mask`.

## Qué se midió

- Tests: 7 pasaron, 4 xfail (fallo esperado, no cuentan como éxito), 0 fallaron.
- `test_monotonia_fifo`: 1000 pares aleatorios sobre `GridWorld`, 0 violaciones.
- `test_held_karp_vs_fuerza_bruta_3_pedidos` / `..._4_pedidos`: exacto contra fuerza bruta en varias semillas.
- `test_held_karp_espera_estrategica`: caso fabricado A MANO (3 pedidos) donde la secuencia de llegada más temprana viola frescura (hueco 980s > theta 600s) pero esperar en el primer comercio la vuelve factible (hueco exacto 600s). Pasa.
- Benchmarks (`python -m vygo.bench`, 200 instancias, calentamiento de JIT excluido del tiempo):
  - `held_karp` 12 paradas: p50≈2.0ms, **p95≈3.2ms** (objetivo <2ms, NO cumplido).
  - `action_mask` 8 ofertas / 6 pedidos activos: p50≈2.4ms, **p95≈3.2ms** (objetivo <15ms, CUMPLIDO).

## Qué falló / optimizaciones aplicadas (en orden)

- Primera versión (DP de Held-Karp con beam K en Python puro): p95 held_karp ≈217ms (108x el objetivo). Perfilado: el cuello de botella era puro overhead de intérprete (creación de tuplas/listas), no las llamadas a `travel_fn`.
- Bitmask de enteros para subconjuntos: ya se usaba desde el inicio.
- JIT con numba del DP (single-best, no beam) sobre una matriz de viaje PRECALCULADA una vez por llamada (snapshot en t0; el pase final de `verificar_y_calendarizar` SIEMPRE usa el travel_fn real dependiente del tiempo, así que esto no compromete la corrección, sólo el ranking/generación de candidatas): 217ms -> 19ms.
- Se detectó y corrigió un bug de no-convergencia en el punto fijo: cuando ninguna espera aguas abajo puede absorber el retraso, el hueco de frescura no mejora nunca y el punto fijo agotaba las 20 iteraciones por candidata sin darse cuenta. Se agregó detección de "no-mejora" para declarar infactible de inmediato: 19ms -> ~4ms, y `candidatas_agotadas` bajó de 167/200 a 16/200 sobre instancias más realistas (paradas en radio local, no esparcidas por toda la rejilla).
- Arrays preasignados en vez de diccionarios por id de pedido en el rankeo de candidatas de perturbación (`_indices_auxiliares`): ~4ms -> ~3.2ms.
- K bajado de 20 a 10 (`ai/CLAUDE.md` §10 lo autoriza explícitamente).
- Con eso agotado, sigue ~1.5x arriba del objetivo de 2ms. Siguiente paso si hace falta más margen: numba también en `_candidatas_por_perturbacion`/`_tiempo_de_orden` (hoy puro Python), o reducir aún más el vecindario de perturbación.

## Qué sigue

- Implementar `vygo/weather.py` (cadena de Markov, 5 estados) y `vygo/generator.py` (llegada de pedidos + difusión por rondas) para tener un `VygoEnv` L0/L1 mínimo.
- Con eso, `vygo/env.py` real y correr `python run.py bench` (objetivo ≥5000 steps/s con 16 entornos) y los tests xfail que dependen de VygoEnv.

## Bloqueos

- vygo/env.py no está implementado: no existe entorno de simulación L0/L1 todavía (geo.py, sequencer.py, insertion.py y feasibility.py ya sí).
- vygo/weather.py, generator.py, features.py, baselines.py, train_ppo.py, evaluate.py, export_vygo.py siguen siendo stubs sin cuerpo.
- held_karp con 12 paradas: p95 ~3.2ms sobre el objetivo de 2ms (ver reports/HANDOFF.md, sección de benchmarks, para el detalle de optimizaciones ya aplicadas y las que faltan).
- baselines B0-B3 no implementados; scenarios/test_50.pkl todavía no existe.

## Siguiente paso sugerido

Implementar vygo/weather.py (cadena de Markov) y vygo/generator.py (llegada de pedidos + difusión por rondas) para tener un VygoEnv mínimo L0/L1.
