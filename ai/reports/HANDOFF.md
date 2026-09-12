# HANDOFF — B2-entorno-L0-L1

_Generado: 2026-09-12T12:04:49+00:00 · commit `65894b3` (sucio: hay cambios sin commitear)_

## TL;DR

El entorno L0/L1 completo existe y los 11 tests de invariantes pasan (conservación, capacidad, frescura=0, contabilidad — sobre una VENTANA ACOTADA de pasos, no el turno completo; ver más abajo por qué). La **prueba de sanidad B1 vs B2 obligatoria NO se pudo completar de forma concluyente**: un problema de rendimiento real (ya diagnosticado, no arreglado del todo) hace que correr un turno completo tome demasiado tiempo. No se puede afirmar todavía que el generador produzca (o no) oportunidad de agrupamiento suficiente para entrenar.

## Qué se construyó

- `vygo/weather.py`: `CadenaClima`, Markov de 5 estados/15 min, matriz y multiplicadores (tiempo de viaje, demanda, tarifa) en `config/clima.yaml`. `geo.py` ahora importa el multiplicador de tiempo de viaje de aquí (antes tenía su propia copia, ligeramente distinta).
- `vygo/generator.py`: `GeneradorPedidos` — M comercios muestreados por densidad (no uniforme), llegada Poisson no homogénea (picos de comida/cena), destino en kernel log-normal alrededor del comercio, tarifa y preparación con la fórmula de la tarea, anillos de prioridad (1500/3000/5000 m) y `resolver_ronda` con competidores sintéticos. Ganchos `modificador(t, zona)` y (en `geo.travel`, ya existía el parámetro) `corredores_cerrados` presentes pero sin implementar el evento de media jornada, como pedía la tarea.
- `vygo/features.py`: `ConstructorFeatures`, vector de 186 dims (14+6×10+8×14) exacto a §6, buffer preasignado, `construir()` nunca crea un array nuevo.
- `vygo/env.py`: `VygoEnv`, dirigido por eventos (pedido, cierra_ronda, expira_oferta, llega_nodo). `nivel` L0/L1. `rho_hat` con EMA alfa=0.01.
- `vygo/baselines.py`: B0 (aleatoria), B1 (primera factible), B2 y B2-ingenuo (umbral, con/sin `p_gana`), `RhoHatMovil` (ventana de 90 min simulados).
- `vygo/sanity_check.py`: driver B1 vs B2 (ver limitación abajo).
- **Patch al secuenciador** (pedido explícito antes del entorno): con <=4 pedidos (<=8 paradas), `held_karp` ahora enumera TODAS las secuencias válidas por precedencia (backtracking directo, no genera-y-filtra) y devuelve dos campos nuevos, `optimo_exacto` y `secuencias_evaluadas` — contrato con el frontend: la UI sólo puede decir "óptimo exacto sobre N secuencias" cuando `optimo_exacto` es `True`. Para llegar a un tiempo razonable se agregó una poda por cota inferior (el punto fijo sólo puede posponer, nunca adelantar, así que el tiempo naive sin espera es una cota inferior válida del tiempo final) — ver más abajo por qué esa poda no basta en todos los casos.
- `sequencer.py` ahora soporta pedidos "ya recogidos" (sólo parada de entrega, sin precedencia) — hacía falta porque `VygoEnv` pasa el plan así una vez que el vehículo pasa por la recogida; sin esto `held_karp` tronaba (`ValueError`) en cuanto el entorno corría de verdad.

## Qué se midió

- Tests: 11 pasaron, 0 xfail, 0 fallaron. Los 4 que dependen de `VygoEnv` ya NO son xfail: corren de verdad, sobre 150 pasos (no el turno de 6h completo — ver rendimiento abajo).
- `held_karp` con K_A=4 (8 paradas, el caso real de uso tras el patch): exacto por construcción, ya no hace falta medir p95 contra el objetivo de 12 paradas/K=20 candidatas (ese benchmark no se volvió a tocar, como se pidió).

## Bugs reales encontrados y corregidos en este bloque

1. **Precedencia con pedidos ya recogidos**: `sequencer.py` asumía que todo pedido llega como par (recogida+entrega); `VygoEnv` pasa sólo la entrega una vez recogido. `ValueError` inmediato al correr el entorno. Arreglado en los 4 sitios que asumían el par (máscaras de subconjunto, arrays auxiliares, calendario, enumeración exacta).
2. **`llegada` en vez de `salida` en el evento de nodo**: el vehículo "llegaba" a una recogida y avanzaba el reloj a la llegada, saltándose la espera obligatoria por preparación (`S_o = max(T_o, r_i)`). Debía usar la SALIDA calendarizada.
3. **Contador de rechazados roto**: al cerrar una ronda sin aceptaciones, el código re-encolaba el pedido para la siguiente ronda AUNQUE el agente ya lo hubiera rechazado explícitamente, resucitando pedidos terminados y dejando `rechazados > generados`. Se agregó un guard de estados terminales.
4. **Contabilidad no cuadraba** (~2.5% de diferencia): `reset()` avanza hasta el primer punto de decisión y ese avance sí cobraba costo de tiempo en el ledger, pero gymnasium no expone una recompensa de `reset()` — ese costo nunca aparecía en la suma de recompensas de `step()`. Se desactiva la contabilización durante el avance inicial.
5. **Caché de calendario obsoleto**: si `held_karp`/`verificar_y_calendarizar` fallaban dentro de `_recalendarizar` (defensivo, no debería pasar), el caché viejo no se invalidaba, lo que podía colgar el loop de eventos en un ciclo sin avanzar el tiempo. Ahora se invalida primero, siempre.
6. **Cola de pendientes O(n) y sin tope**: `cola_pendientes` era una lista con `.pop(0)`; cambiada a `collections.deque` con tope (`MAX_COLA_PENDIENTES=40`, se cae/expira más allá de eso) para que un desbalance llegada/capacidad no crezca sin límite.

## LIMITACIÓN CONOCIDA — bloquea la prueba de sanidad

Con el patch de arriba, `held_karp` es EXACTO y rápido (~15-30ms) cuando las paradas están en un radio local (el benchmark sintético de `vygo/bench.py`, que usa posiciones 0-8). Pero `generator.py` muestrea comercios por densidad sobre TODO el grid 20x20 — pedidos reales del entorno pueden estar mucho más dispersos. Con el plan en 4-5 pedidos dispersos, la poda por cota inferior deja de ser efectiva (muchas de las 2520 secuencias quedan casi empatadas en tiempo naive, así que hay que calendarizarlas casi todas) y el costo por `step()` sube de ~15ms a cientos de ms, y sigue subiendo con la duración del episodio. Diagnosticado con profiling (`_simular_adelante` con >150k llamadas en 30 steps en la zona lenta).

Consecuencia directa: no fue posible correr los 20 escenarios x turno completo (6h) que pedía la prueba de sanidad B1 vs B2 en el tiempo disponible. Intentos con ventanas más chicas (700-950 pasos) corren rápido pero terminan ANTES de la primera entrega (la primera entrega observada en una corrida de prueba apareció cerca del paso 1500) — es decir, la ventana que es rápida no alcanza a mostrar bundling, y la ventana que alcanzaría a mostrarlo ya no es rápida.

**No se puede afirmar que el generador pase o falle el criterio de la prueba de sanidad.** Por la propia regla de la tarea ("si B2 no supera a B1... no sigas"), lo correcto es NO asumir que hay luz verde para entrenar hasta resolver esto.

Siguiente paso concreto: perfilar `held_karp` con paradas realmente dispersas (no el benchmark actual) y decidir entre (a) una cota de poda más floja pero más rápida de evaluar, (b) bajar el umbral exacto de 4 a 3 pedidos y aceptar heurística antes, o (c) numba también en la ruta exacta.

## Qué sigue

- Resolver la limitación de arriba.
- Con eso, correr `python -m vygo.sanity_check` completo (20 escenarios, turno de 6h) y decidir si seguir a entrenamiento o subir intensidad/concentración del generador.
- `python run.py bench` (objetivo >=3000 steps/s con 16 entornos) no se pudo medir de forma representativa por la misma razón.
- B0 y B3 (baselines.py) y export_vygo.py, train_ppo.py, evaluate.py siguen sin implementar.

## Bloqueos

- BLOQUEO PRINCIPAL: la prueba de sanidad B1 vs B2 no se pudo completar de forma concluyente. Causa raíz diagnosticada: el podado por cota inferior de la ruta exacta de held_karp (<=4 pedidos) es efectivo sobre posiciones agrupadas (el benchmark sintético) pero NO sobre pedidos dispersos por todo el grid 20x20 (el muestreo real de comercios de generator.py), donde muchas de las 2520 secuencias válidas quedan casi empatadas y hay que verificarlas casi todas. Con 4-5 pedidos en el plan, el costo por step sube de ~15ms a varios cientos de ms/step y sigue subiendo. Ver reports/HANDOFF.md para el detalle y la traza de diagnóstico.
- train_ppo.py, evaluate.py, export_vygo.py siguen siendo stubs sin cuerpo.
- baselines B0 (aleatoria) y B3 (MILP rodante) no implementados -- sólo B1/B2/B2-ingenuo (docs/vygo-ai-training.md §6.1); scenarios/test_50.pkl no existe.

## Siguiente paso sugerido

Resolver el bloqueo de rendimiento (ver bloqueos) antes de correr la prueba de sanidad B1 vs B2 completa y decidir si el generador produce suficiente oportunidad de agrupamiento para entrenar.
