# HANDOFF — B2-insercion-barata-y-decision-por-ronda

_Generado: 2026-09-12T13:36:29+00:00 · commit `e6f01a1` (sucio: hay cambios sin commitear)_

## TL;DR

El bloqueo de rendimiento del bloque anterior era un diagnóstico equivocado a medias: no era que `held_karp` fuera lento, era **cuántas veces se llamaba** (una vez por cada una de las 8 ofertas visibles, por step, re-enumerando el plan entero cada vez). Se arregló con inserción clásica barata + prefiltro + una sola decisión por cierre de ronda + tope duro K_A. Resultado: de ~7-30 steps/s (y episodios que se colgaban) a **p95 de step()=1.04ms, ~1500 steps/s con 16 entornos**. La prueba de sanidad SÍ corrió esta vez, completa, con turnos de 2h: el generador **no pasa el criterio de agrupamiento** todavía (B2 sólo +9.3% sobre B1, bundling=0.97). Un intento rápido de retunear no lo resolvió. No hay luz verde para entrenar; falta otra vuelta al generador.

## El bug real (por qué estaba lento)

`eval_insertion` llamaba a `held_karp` completo (hasta 2520 secuencias) por cada una de las 8 ofertas visibles, en CADA step. Con un episodio de 6h generando miles de pedidos, eso son decenas de miles de enumeraciones completas. El fix no fue optimizar `held_karp` más (ya se había hecho todo lo razonable en el bloque anterior) sino dejar de llamarlo tanto:

1. **Tope duro K_A**: el plan activo nunca pasa de `K_A_MAXIMO` pedidos (`sequencer.UMBRAL_EXACTO_PEDIDOS`, ahora pública). Con el plan lleno, `action_mask` marca las 8 ofertas infactibles sin evaluar nada. Assert defensivo en `env._aceptar_oferta`.
2. **Inserción clásica barata** (`insertion.mejor_insercion`): para evaluar una oferta ya NO se re-enumera el plan completo. Se toma el orden VIGENTE del plan (el que dejó la última reoptimización exacta) y se prueba insertar el par (recogida_j, entrega_j) en cada posición válida de ESE orden fijo -- con el plan lleno menos un pedido, (m+1)(m+2)/2 combinaciones (28 con m=6), no 2520. La reoptimización EXACTA completa (`held_karp`) sólo se corre UNA vez, al comprometer una oferta aceptada (`env._recalendarizar`). `baseline_plan` dejó de llamar a `held_karp` también: como el plan ya está en su orden óptimo, sólo hace falta calendarizarlo (barato), no re-derivarlo.
3. **Prefiltro**: de las hasta 8 ofertas visibles, sólo se calendarizan (con `eval_insertion`, ya barato) las `N_PREFILTRO=3` mejores por un puntaje GEOMÉTRICO puro (desvío en línea recta / tarifa, cero calendarización). Las otras 5 quedan infactibles sin evaluarse -- el agente las sigue viendo en la observación con sus features baratos (delta, tarifa, anillo, p_gana).
4. **Una decisión por cierre de ronda, no por oferta**: `_avanzar_hasta_decision` ya no le devuelve el turno al agente en cada llegada de pedido o expiración de oferta -- sólo cuando cierra una ronda (evento `cierra_ronda`). Antes, cada pedido generaba su propia época de decisión.
5. **Guardia de tiempo en `held_karp`**: el camino exacto aborta a los 25ms (`_LIMITE_TIEMPO_EXACTO_S`) y devuelve lo mejor YA VERIFICADO hasta ese punto con `optimo_exacto=False` -- nunca una secuencia sin verificar (arriesgaría `violaciones_frescura`).

## Un bug real encontrado AL MEDIR (no cosmético)

Con K_A=4, `held_karp` a veces topaba la guardia de 25ms en pedidos genuinamente dispersos (confirmado: sin la guardia, la misma instancia sí es factible, tarda 58ms). `env._recalendarizar()` simplemente devolvía sin actualizar el horario, dejando el plan con paradas pero SIN horario -- `_proximo_evento_nodo` nunca volvía a encontrar un evento y el vehículo quedaba CONGELADO el resto del episodio (síntoma: `entregados=0` tras 5000 steps con miles de pedidos rechazados). Arreglado: `_recalendarizar` ahora devuelve `bool`; si la reoptimización exacta no puede confirmarse a tiempo, `_aceptar_oferta` REVIERTE la aceptación (el pedido queda 'perdido') en vez de dejar un plan sin horario.

## Mediciones (después de cada punto, con K_A=4 primero)

- Suite de tests: 41-46s -> **1.6-2.1s** (11 tests).
- Episodio completo (B1, 5000 steps, un solo proceso): antes se colgaba/no entregaba nada; con el fix de reversión, 547.7 steps/s, 15 entregas reales en 3.4h simuladas.
- `python -m vygo.env --bench` (16 entornos, K_A=4): **775.7 steps/s** -- por encima del piso de 300 pero debajo del objetivo real de 1000.
- K_A bajado de 4 a 3 (autorizado explícitamente por la tarea si no se llega a 1000): **1500-1618 steps/s**, muy por encima del objetivo. Documentado en el comentario de `sequencer.UMBRAL_EXACTO_PEDIDOS`. Los tests que asumían el camino exacto a 4 pedidos se actualizaron (4 pedidos ahora usa el camino heurístico; sigue encontrando el óptimo real en las instancias de prueba, pero ya no está garantizado, así que `exacto` se afloja a `False` ahí).
- p95 de `step()`: **1.042ms** (p50=0.28ms, p99=2.39ms, máximo observado 12.1ms). Sin cuelgues.

## Prueba de sanidad (punto 7) -- 20 escenarios, turno de 2h, L0

| política | rho_mediana | bundling | entregados/turno |
|---|---|---|---|
| B1 | 282.73 | 0.98 | 8.2 |
| B2 | 308.93 | 0.97 | 8.8 |
| B2-ingenuo | 312.91 | 0.97 | 8.9 |

B2 vs B1: **+9.3%** (umbral 15%). B2 vs B2-ingenuo: **-1.3%** (o sea, entender `p_gana` NO ayudó aquí -- esperable: en L0 `n_competidores_base=0`, así que `p_gana_estimada` da 1.0 siempre y esa comparación no es significativa en L0; haría falta L1 para medirla de verdad). factor_agrupamiento(B2)=0.97 (umbral 1.4, y <1.0 significa que en promedio va MENOS de 1 pedido a bordo).

**ALERTA de la propia tarea: el generador no produce oportunidad de agrupamiento suficiente.** Se intentó un retuneo rápido (intensidad de llegada x3, techo de preparación 25->35 min) y se volvió a medir con una muestra más chica (5 escenarios, no 20, por presupuesto de tiempo: cada escenario ahora tarda ~5x más en simular con más pedidos): +3.4% B2 vs B1, bundling=0.92 -- sin mejora clara (la muestra es demasiado chica para concluir que empeoró de verdad, pero tampoco hay evidencia de que haya ayudado). El cambio de intensidad/preparación se dejó en el código (es una mejora razonable de todos modos) pero NO resuelve el problema por sí solo.

**No hay luz verde para entrenar.** Por la propia regla de la tarea, el siguiente paso es seguir ajustando el generador -- la palanca que falta probar es CONCENTRAR geográficamente el muestreo de comercios (`generator.muestrear_comercios` ya pondera por densidad, pero la densidad en sí está esparcida por todo el grid 20x20; achicar el área de alta densidad debería ser más efectivo que subir la intensidad).

## Qué sigue

- Concentrar geográficamente los comercios y volver a correr `python -m vygo.sanity_check` completo (20 escenarios) antes de tocar entrenamiento.
- B0 (aleatoria) y B3 (MILP rodante), export_vygo.py, train_ppo.py, evaluate.py siguen sin implementar.

## Bloqueos

- BLOQUEO PRINCIPAL: la prueba de sanidad SÍ se completó esta vez (20 escenarios, turno de 2h, entorno ya rápido) y el generador NO pasa el criterio: B2 sólo supera a B1 por +9.3% (umbral 15%) y factor_agrupamiento(B2)=0.97 (umbral 1.4). Un intento de retunear (intensidad de llegada x3, techo de preparación 25->35 min) no mostró mejora clara sobre una muestra más chica (5 escenarios, por presupuesto de tiempo): +3.4%, bundling=0.92. No se investigó más a fondo (p.ej. concentrar geográficamente los comercios, la palanca que falta probar). Conclusión: NO hay evidencia de que el generador produzca oportunidad de agrupamiento suficiente para entrenar todavía. Ver reports/HANDOFF.md.
- En L0 no hay competidores sintéticos (n_competidores_base=0 por diseño), así que p_gana_estimada=1.0 siempre y la comparación B2 vs B2-ingenuo no es significativa en L0 -- hace falta L1 para medirla de verdad.
- train_ppo.py, evaluate.py, export_vygo.py siguen siendo stubs sin cuerpo.
- baselines B0 (aleatoria) y B3 (MILP rodante) no implementados -- sólo B1/B2/B2-ingenuo (docs/vygo-ai-training.md §6.1); scenarios/test_50.pkl no existe.

## Siguiente paso sugerido

Concentrar geográficamente el muestreo de comercios (generator.muestrear_comercios) para crear oportunidad de agrupamiento real, y volver a correr la prueba de sanidad completa antes de considerar entrenamiento.
