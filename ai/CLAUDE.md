# VYGO-RL — Constitución del agente

> Vive en `ai/` dentro del monorepo VYGO. Es el contrato de esta parte del proyecto.
> **No renombres archivos ni cambies firmas públicas sin actualizar este documento primero.**

## 0. Contexto del monorepo y límites de trabajo

Este repositorio contiene también el frontend de VYGO (Vite + React + TypeScript + Tailwind) en
`src/`, mantenido por otra persona en paralelo.

**Reglas duras, sin excepción:**

1. **Todo lo que escribas vive bajo `ai/`.** No toques `src/`, `package.json`, `index.html`,
   `vite.config.ts`, `tailwind.config.js` ni ningún archivo de la raíz.
2. **Trabajamos en la rama `ai/rl-agent`.** Verifica con `git branch --show-current` antes de
   hacer cualquier commit. Si estás en `main`, detente y avisa.
3. **Nunca corras `npm`, `npx`, `vite` ni builds del frontend.** No es tu stack.
4. **Los mensajes de commit llevan prefijo `ai:`** para que el historial sea separable.
5. Si una tarea parece requerir tocar el frontend, **no lo hagas**: descríbelo en
   `ai/reports/HANDOFF.md` bajo "pendientes para el frontend" y sigue con lo tuyo.

**Superficie de contacto con el frontend**, la única: el frontend *lee* `ai/reports/status.json`
y los archivos de `ai/demo/`. Nunca los escribe. Mantén ese contrato estable.

**Esquema de base de datos:** `docs/vygo-ai-training.pdf` en la raíz del repo es la fuente de
verdad. El frontend y el simulador comparten tablas, columnas, enums y estados.

## 1. Qué estamos construyendo

Un agente de RL que decide **aceptar / rechazar / reposicionar** ofertas de reparto que llegan
desde 3 plataformas (uber, didi, rappi), para maximizar la **tasa de ganancia del repartidor
(MXN/hora)**, no la ganancia total ni la distancia.

El sistema es un **middleware**: no genera datos, sólo optimiza decisiones sobre ofertas que
las plataformas ya emiten.

## 1.1 Documentos de referencia (léelos sólo cuando el prompt te lo pida)

- `../docs/vygo-ai-training.pdf` — esquema real de la base de datos VYGO (tablas, columnas,
  enums, CHECKs, DDL completo). Consúltalo al escribir `schema.py` y `export_vygo.py`.
- `../docs/modelo-matematico.md` — formulación MILP y SMDP completa, con la derivación de la
  regla de aceptación por umbral. Consúltalo si dudas de una restricción o de la recompensa.

No los leas por defecto: gastan contexto. Este archivo tiene todo lo necesario para el día a día.

## 2. Reglas no negociables

1. **La secuenciación NO se aprende.** Se resuelve exacto con Held–Karp (≤12 paradas).
   La red sólo decide aceptar/rechazar/reposicionar.
2. **Las restricciones duras NO se aprenden.** Frescura, capacidad y precedencia se imponen
   con una **máscara de factibilidad exacta**. `violaciones_frescura` debe ser 0 SIEMPRE.
   Si no es 0, es un bug, no un problema de entrenamiento.
3. **Nunca se premia moverse, aceptar o recoger.** El dinero sólo entra al **entregar**.
   Ver antipatrones en §7.
4. **Todo tiempo cuesta.** La recompensa lleva el término `- rho_hat * dt`. Sin él, el agente
   acepta trabajos de tasa horaria pésima.
5. **El entorno es NumPy puro en L0/L1.** Nada de pandas, dict, ni asignación de memoria
   dentro de `step()`. Objetivo: **≥5000 steps/s con 16 entornos**.
6. **Nunca se entrena en L2.** L2 (red vial real de Monterrey vía OSMnx) es sólo para la
   demo visual y la evaluación final. El entrenamiento ocurre en L0/L1.
7. **Semillas separadas** para train / val / test. Los 50 escenarios de test se congelan una
   vez y no se tocan jamás para elegir hiperparámetros.
8. **Cada bloque de trabajo termina regenerando `reports/HANDOFF.md` y `reports/status.json`.**
   Ese es el entregable que se revisa fuera del repo.

## 3. Vocabulario — espejo del esquema VYGO (Supabase/PostGIS)

El simulador usa **exactamente** los mismos nombres, estados y enums que la base de datos de
producción. Esto no es cosmético: permite volcar episodios simulados a la BD real y que el
agente entrenado se conecte sin capa de traducción.

```
apps            : id ∈ {1:uber, 2:didi, 3:rappi}
pedido.estado   : creado → buscando → asignado → en_camino → entregado | cancelado
oferta.estado   : pendiente | aceptada | rechazada | expirada | perdida | cancelada
difusion.resultado : aceptada | sin_respuesta | cancelada
clima           : despejado | nublado | lluvia | lluvia_fuerte | tormenta | otro   (5 usables)
vehiculo        : moto | auto | bici
```

**Mecanismo de difusión (clave del problema).** La notificación de un pedido se envía a **todos**
los repartidores disponibles. Lo que los `radio_metros` de `difusiones_pedido` definen son
**anillos de prioridad** por distancia vectorial al origen del pedido:

```
anillo 1: distancia <= 1500 m     ← prioridad máxima
anillo 2: distancia <= 3000 m
anillo 3: distancia <= 5000 m
fuera:    no elegible
```

Entre todos los que aceptan, **gana el del anillo más interno**; dentro del mismo anillo gana el
más cercano (desempate por `respondida_en` si hay empate de distancia). Los demás que aceptaron
pasan a `estado='perdida'`.

Consecuencias de modelado, las tres importantes:

1. **Aceptar ≠ obtener.** El valor esperado de aceptar la oferta `j` es
   `P_gana(j) * ganancia_marginal(j)`, con `P_gana` función del anillo y del número de
   competidores más cercanos. Una oferta con tasa marginal excelente pero en anillo 3 vale poco.
2. **El valor de posición sigue existiendo**, pero por otra vía: estar en zona densa no aumenta
   cuántas ofertas *ves*, aumenta en cuántas caes en el **anillo 1**. Ésa es la variable que la
   acción `reposicionarse` controla y lo que el RL debe aprender.
3. **Aceptar tiene un costo real aunque pierdas:** la asignación se resuelve al cierre de la
   ronda (45 s). Durante esa ventana quedas comprometido y no puedes planear en firme. Aceptar
   de más te congela; aceptar de menos te deja sin trabajo.

Se permite aceptar varias ofertas en la misma ronda (es lo que hacen los repartidores reales).
La máscara sólo exige que el conjunto de ofertas aceptadas sea **conjuntamente factible** en el
peor caso, es decir, si las ganaras todas.

## 4. Estructura de `ai/`

```
ai/
├── CLAUDE.md                  ← este archivo
├── requirements.txt
├── config/
│   ├── env_l0.yaml            # rejilla, sin clima, sin preparación
│   ├── env_l1.yaml            # zonas de densidad, preparación, clima, difusión por rondas
│   ├── env_l2.yaml            # red vial real MTY (sólo demo/eval)
│   └── ppo.yaml
├── vygo/
│   ├── schema.py              # dataclasses espejo de la BD + enums
│   ├── geo.py                 # rejilla, zonas, matrices de tiempo/distancia
│   ├── weather.py             # cadena de Markov de 5 estados
│   ├── generator.py           # llegada de pedidos + difusión por rondas
│   ├── sequencer.py           # Held–Karp exacto
│   ├── insertion.py           # Δt_j, Δδ_j óptimos por oferta
│   ├── feasibility.py         # máscara exacta
│   ├── env.py                 # VygoEnv (gymnasium)
│   ├── baselines.py           # B0, B1, B2, B3
│   ├── features.py            # construcción del vector de observación
│   ├── train_ppo.py
│   ├── evaluate.py            # protocolo pareado sobre escenarios congelados
│   ├── report.py              # genera reports/status.json + HANDOFF.md
│   └── export_vygo.py         # vuelca episodios al esquema VYGO (SQL/CSV)
├── tests/test_invariants.py
├── scenarios/test_50.pkl      # congelado, nunca regenerar
└── reports/
    ├── status.json            # legible por máquina
    ├── HANDOFF.md             # legible por humano/LLM
    ├── metrics.csv
    └── train_log.jsonl
```

## 5. Firmas públicas (no cambiar sin actualizar aquí)

```python
# sequencer.py
def held_karp(stops, t0, pos0, travel_fn, constraints, k=10) -> tuple[list[int], float, float, bool, int]:
    """Devuelve (orden_óptimo, tiempo_total, distancia_total, optimo_exacto, secuencias_evaluadas).
    Si no existe secuencia factible: (None, inf, inf, optimo_exacto, secuencias_evaluadas).
    <=UMBRAL_EXACTO_PEDIDOS pedidos (hoy 3, <=6 paradas): enumeración exacta de todas las
    secuencias válidas por precedencia -- optimo_exacto=True, secuencias_evaluadas=las que
    había que enumerar (90 con 3 pedidos). Más que eso: camino heurístico (DP +
    perturbación), optimo_exacto=False. Contrato con el frontend: la UI sólo puede decir
    "óptimo exacto sobre N secuencias" cuando optimo_exacto es True.

    UMBRAL_EXACTO_PEDIDOS es una decisión de ALGORITMO, NO el tope de cuántos pedidos caben
    en el plan activo -- ese es feasibility.K_A_MAXIMO (hoy 4), independiente a propósito
    desde la tarea "diagnostico de agrupamiento": con K_A_MAXIMO > UMBRAL_EXACTO_PEDIDOS,
    el plan puede tener un pedido más que lo que held_karp resuelve exacto, calendarizado
    por el camino heurístico (rápido, sin garantía de óptimo)."""

# insertion.py
def eval_insertion(plan, oferta, estado) -> tuple[float, float, bool]:
    """Devuelve (delta_t_segundos, delta_dist_metros, factible)."""

# feasibility.py
def action_mask(estado) -> np.ndarray:      # shape (K_F + 2,), dtype bool
K_A_MAXIMO = 4   # tope de pedidos en el plan activo (problema, no algoritmo)

# env.py
class VygoEnv(gymnasium.Env):
    """obs: Box(float32); action: Discrete(K_F + 2)
    K_F = 8 ofertas visibles; acción K_F = rechazar-todas; K_F+1 = reposicionarse."""

# baselines.py
def politica_umbral(estado, rho_hat) -> int   # B2

# report.py
def write_report(run_dir: str) -> None
```

## 6. Acción y observación

**Acción:** `Discrete(10)` = 8 ofertas + `rechazar_todas` + `reposicionarse`.

**Observación:** vector plano `float32`, concatenación de:

| Bloque | Dims | Contenido |
|---|---|---|
| propio | 14 | x, y normalizadas, carga/Q, t transcurrido, t restante, `rho_hat`, ganancia acum., km acum., clima one-hot (5), densidad local |
| plan activo | 6 × 10 | por pedido: Δ a origen (2), Δ a destino (2), tarifa norm., holgura frescura, holgura fecha límite, `r_i - t`, recogido?, app one-hot comprimida |
| ofertas | 8 × 14 | Δ a origen (2), Δ a destino (2), tarifa, tarifa/km, **`delta_t`**, **`delta_dist`**, **tasa marginal**, **`anillo` (1/2/3 normalizado)**, **`p_gana_estimada`**, `r_j - t`, seg. para expirar, factible? |

**Las tres columnas en negrita son el 80 % del valor.** Le entregan a la red el numerador y el
denominador de la regla de umbral ya calculados. Sin ellas la red tiene que aprender geometría
de rutas desde coordenadas, lo que cuesta un orden de magnitud más de muestras.

Relleno con ceros + máscara para slots vacíos. Normalizar con `VecNormalize`, estadísticas
**congeladas en evaluación**.

## 7. Recompensa

```
r_k = Σ_entregados (tarifa + propina)          # única fuente de ingreso
    - c_kappa * delta_dist_km
    - Σ psi_i * max(0, T_entrega - limite_i)
    - rho_hat * delta_t_horas                   # precio del tiempo
```

`rho_hat`: media móvil de la tasa realizada del propio agente (estilo R-learning), inicializada
en 100 MXN/h.

**Antipatrones — si ves el síntoma, es esto:**

| Síntoma en `status.json` | Causa | Arreglo |
|---|---|---|
| `tasa_aceptacion ≈ 0` | colapso inicial: rechazar da 0, que es mejor que aceptar mal | arranque por imitación, subir entropía |
| `tasa_aceptacion ≈ 1` y `puntualidad` baja | hay bonus por aceptar, o `psi` muy baja | quitar bonus, subir `psi` |
| `pedidos_por_hora` alto y `rho` bajo | falta el término `- rho_hat*dt` | añadirlo |
| `km_vacios` alto | se premia moverse | nunca premiar movimiento |
| `violaciones_frescura > 0` | **bug en la máscara** | no es RL, es código |
| `factor_agrupamiento ≈ 1.0` | el generador no crea solapamiento | subir intensidad / concentrar comercios |

## 8. Contrato de reporte — `reports/status.json`

Se regenera al final de cada bloque y cada N pasos durante el entrenamiento. Debe poder
copiarse y pegarse completo en un chat: **máximo ~150 líneas**.

```json
{
  "generado_en": "ISO-8601",
  "bloque": "B3-baselines",
  "commit": "abc1234",
  "entorno": {"nivel": "L1", "config_hash": "...", "steps_por_segundo": 6200},
  "tests": {"pasaron": 14, "fallaron": 0, "xfail": 0, "detalle_fallos": []},
  "invariantes": {
    "violaciones_frescura": 0,
    "violaciones_capacidad": 0,
    "fifo_ok": true,
    "contabilidad_ok": true,
    "holdout_intacto": true
  },
  "baselines": {
    "B0": {"rho": 61.2, "pedidos_h": 1.1, "puntualidad": 0.55, "bundling": 1.0},
    "B1": {"rho": 88.4, "...": null},
    "B2": {"rho": 143.7, "...": null},
    "B3": {"rho": 0, "estado": "no_implementado"}
  },
  "entrenamiento": {
    "activo": true,
    "algoritmo": "MaskablePPO",
    "semillas": [0, 1, 2],
    "pasos_totales": 1850000,
    "pasos_objetivo": 8000000,
    "eta_minutos": 190,
    "curva": [{"paso": 100000, "rho_val": 95.1, "aceptacion": 0.12, "entropia": 1.9,
               "kl": 0.011, "varianza_explicada": 0.31}],
    "mejor_rho_val": 151.3,
    "etapa_curriculum": 3
  },
  "evaluacion": {
    "escenarios": 50, "pareada": true,
    "agente": {"rho_mediana": 0, "iqr": [0, 0]},
    "vs_B2_pct": null,
    "gap_vs_oraculo": null
  },
  "diagnostico_automatico": ["texto legible de cada antipatrón detectado"],
  "bloqueos": ["qué impide avanzar ahora mismo"],
  "siguiente_paso_sugerido": "una frase"
}
```

**Los `xfail` NO cuentan como `pasaron`.** Un test marcado `xfail` es un test que aún no puede
pasar; contarlo como éxito produce un tablero en verde que miente. Van en su propio campo.

`HANDOFF.md` es la versión narrada de lo mismo: qué se construyó, qué se midió, qué falló, qué
sigue. Máximo 2 páginas. **Se escribe para alguien que no ha visto el código.**

## 9. Orden de sacrificio si falta tiempo

Recortar en este orden, sin discusión: L3/SUMO → B4 oráculo MILP → incidentes de tráfico →
canal espacial convolucional → aleatorización de dominio → clima. **Nunca recortar:** máscara
exacta, Held–Karp, B2, evaluación pareada.

## 10. Comandos

El equipo trabaja en **Windows 10**, donde `make` no está disponible. El punto de entrada es
`ai/run.py`, con subcomandos. Funciona igual en Windows, macOS y Linux.

```bash
python run.py test              # pytest tests/ -q
python run.py bench             # mide steps/s del entorno
python run.py baselines         # corre B0..B2 sobre los 50 escenarios congelados
python run.py train --seed 0    # entrenamiento
python run.py eval              # evaluación pareada final
python run.py report            # regenera reports/
```

Se mantiene un `Makefile` como envoltura delgada de los mismos subcomandos, para quien tenga
`make`. **`run.py` es la referencia; el Makefile nunca debe tener lógica propia.**

Nada de rutas con `/` escritas a mano ni `os.system`: usa `pathlib.Path` y `subprocess.run` con
listas de argumentos, para que todo funcione en Windows sin cambios.
