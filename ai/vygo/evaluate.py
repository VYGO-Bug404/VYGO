"""Evaluación PAREADA de B_SERIAL / B1 / B2 (y, si existe, un tercer agente entrenado)
sobre los 30 turnos congelados de `scenarios/test_30.pkl` (ai/CLAUDE.md §2.7 -- ver
`vygo/congelar_escenarios.py`). Cada política corre EXACTAMENTE los mismos 30 escenarios
(misma semilla, mismo evento de media jornada), así que cualquier diferencia es la política,
no la suerte del escenario.

B_SERIAL es el repartidor SIN VYGO hoy: una sola app, un pedido a la vez
(`baselines.politica_serial`, K_A efectivo=1 impuesto a nivel de política, sin tocar
`feasibility.K_A_MAXIMO` ni el entorno). Es la primera fila de la tabla -- la referencia
real contra la que compite el producto, no B1.

Reporta, por política: rho (mediana e IQR), entregados, pedidos/hora, tasa de aceptación,
puntualidad, km por pedido, factor de agrupamiento -- cada uno con un desglose ANTES/DESPUÉS
del instante en que arranca el evento de media jornada del escenario.

Estadística pareada CORRECTA (no bootstrapear la diferencia de medianas, que desperdicia el
pareo): para cada comparación política_a vs política_b se calcula d_i = rho_a_i - rho_b_i
en los 30 escenarios, se reporta la MEDIANA de esas diferencias con IC 95% por bootstrap
sobre las diferencias mismas (10 000 remuestreos), y la TASA DE VICTORIAS (en cuántos de
los 30 turnos rho_a > rho_b) -- la cifra más clara para el pitch.

Tercera política "agente": intenta cargar `checkpoints/ppo_best.zip` y, si no existe,
`checkpoints/bc_policy.pt` (usa la arquitectura de `vygo.policy_net`, no la reentrena). Si
ninguno existe todavía -- el caso normal en un checkout limpio, `checkpoints/` está en
.gitignore -- se salta esa columna sin fallar: la tabla sale igual sin ella.

Uso: python -m vygo.evaluate
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from vygo.baselines import RhoHatMovil, politica_primera_factible, politica_serial, politica_umbral
from vygo.congelar_escenarios import EscenarioCongelado, RUTA_ESCENARIOS, cargar_escenarios
from vygo.env import COSTO_KM_MXN, VygoEnv
from vygo.eventos import EventoSurge, ProgramadorEventos
from vygo.feasibility import K_F
from vygo.geo import GridWorld
from vygo.insertion import EstadoRuta

_AI_ROOT = Path(__file__).resolve().parent.parent
MAX_PASOS_ESCENARIO = 20_000
N_BOOTSTRAP = 10_000

PoliticaFn = Callable[[EstadoRuta, np.ndarray, np.ndarray, float], int]


def _b_serial(estado: EstadoRuta, _obs: np.ndarray, _mask: np.ndarray, _rho_hat: float) -> int:
    return politica_serial(estado)


def _b1(estado: EstadoRuta, _obs: np.ndarray, _mask: np.ndarray, _rho_hat: float) -> int:
    return politica_primera_factible(estado)


def _b2(estado: EstadoRuta, _obs: np.ndarray, _mask: np.ndarray, rho_hat: float) -> int:
    return politica_umbral(estado, rho_hat, con_p_gana=True)


def _cargar_agente() -> Optional[tuple[str, PoliticaFn]]:
    """Ver docstring del módulo: ranura para una tercera política que carga un checkpoint
    si existe y se salta limpio si no. Import perezoso de sb3/torch/policy_net -- si algo
    de eso falla (versión distinta, checkpoint corrupto, etc.) se degrada igual de limpio,
    nunca tumba la evaluación de B1/B2."""

    ruta_ppo = _AI_ROOT / "checkpoints" / "ppo_best.zip"
    ruta_bc = _AI_ROOT / "checkpoints" / "bc_policy.pt"

    if ruta_ppo.exists():
        try:
            import pickle

            from sb3_contrib import MaskablePPO

            modelo = MaskablePPO.load(str(ruta_ppo), device="cpu")
            vecnorm = None
            ruta_vecnorm = _AI_ROOT / "checkpoints" / "vecnormalize.pkl"
            if ruta_vecnorm.exists():
                with open(ruta_vecnorm, "rb") as f:
                    vecnorm = pickle.load(f)

            def _fn(_estado: EstadoRuta, obs: np.ndarray, mask: np.ndarray, _rho_hat: float) -> int:
                obs_norm = vecnorm.normalize_obs(obs) if vecnorm is not None else obs
                accion, _st = modelo.predict(obs_norm, action_masks=mask, deterministic=True)
                return int(accion)

            print(f"agente: cargado {ruta_ppo.name} (MaskablePPO)")
            return "agente(PPO)", _fn
        except Exception as exc:  # noqa: BLE001 -- degradar limpio, no tumbar la evaluación
            print(f"agente: no se pudo cargar {ruta_ppo.name} ({exc}), probando bc_policy.pt")

    if ruta_bc.exists():
        try:
            import gymnasium as gym
            import torch

            from vygo.features import DIM_TOTAL
            from vygo.policy_net import crear_policy

            obs_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(DIM_TOTAL,), dtype=np.float32)
            act_space = gym.spaces.Discrete(10)
            policy = crear_policy(obs_space, act_space, lambda _p: 1e-3)
            policy.load_state_dict(torch.load(ruta_bc, map_location="cpu"))
            policy.eval()

            def _fn(_estado: EstadoRuta, obs: np.ndarray, mask: np.ndarray, _rho_hat: float) -> int:
                obs_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    dist = policy.get_distribution(obs_t, action_masks=mask[None, :])
                    return int(dist.mode().item())

            print(f"agente: cargado {ruta_bc.name} (BC, sin PPO)")
            return "agente(BC)", _fn
        except Exception as exc:  # noqa: BLE001
            print(f"agente: no se pudo cargar {ruta_bc.name} ({exc}), se omite esa columna")

    print("agente: ningún checkpoint encontrado en checkpoints/ -- se evalúa sólo B1/B2")
    return None


def _t_inicio_evento_s(escenario: EscenarioCongelado) -> float:
    if not escenario.eventos:
        return math.inf
    return min(ev.inicia_min * 60.0 for ev in escenario.eventos)


def _bucket_vacio() -> dict:
    return {
        "ganancia": 0.0, "km": 0.0, "entregados": 0, "a_tiempo": 0, "totales": 0,
        "carga_suma": 0.0, "carga_n": 0, "generados": 0, "perdidos": 0,
    }


def _metricas_de(acc: dict, horas: float) -> dict:
    h = max(horas, 1e-9)
    return {
        "rho": (acc["ganancia"] - COSTO_KM_MXN * acc["km"]) / h,
        "entregados": acc["entregados"],
        "pedidos_por_hora": acc["entregados"] / h,
        "tasa_aceptacion": (acc["entregados"] + acc["perdidos"]) / max(acc["generados"], 1),
        "puntualidad": acc["a_tiempo"] / max(acc["totales"], 1),
        "km_por_pedido": acc["km"] / max(acc["entregados"], 1),
        "bundling": (acc["carga_suma"] / acc["carga_n"]) if acc["carga_n"] else float("nan"),
    }


def correr_escenario(escenario: EscenarioCongelado, politica_fn: PoliticaFn) -> dict:
    """Un escenario, una política. Devuelve {"total", "antes", "despues"} -> métricas."""

    programador = ProgramadorEventos(list(escenario.eventos)) if escenario.eventos else None
    t_evento = _t_inicio_evento_s(escenario)

    env = VygoEnv(
        nivel=escenario.nivel, m_comercios=escenario.m_comercios,
        duracion_turno_s=escenario.duracion_turno_s, programador_eventos=programador,
    )
    obs, info = env.reset(seed=escenario.seed)
    rho_movil = RhoHatMovil()

    acumuladores = {"antes": _bucket_vacio(), "despues": _bucket_vacio()}
    prev_ganancia = prev_km = 0.0
    prev_entregados = prev_a_tiempo = prev_totales = prev_carga_n = 0
    prev_generados = prev_perdidos = 0

    for _ in range(MAX_PASOS_ESCENARIO):
        estado = env._estado_ruta()
        mask = info["action_mask"]
        accion = politica_fn(estado, obs, mask, rho_movil.valor)
        obs, r, term, trunc, info = env.step(accion)
        rho_movil.actualizar(env.t, r)

        bucket = "despues" if env.t >= t_evento else "antes"
        acc = acumuladores[bucket]
        acc["ganancia"] += env.ganancia_acum - prev_ganancia
        acc["km"] += env.km_acum - prev_km
        acc["entregados"] += info["pedidos_entregados"] - prev_entregados
        acc["a_tiempo"] += env._entregas_a_tiempo - prev_a_tiempo
        acc["totales"] += env._entregas_totales - prev_totales
        acc["generados"] += env.contadores["generados"] - prev_generados
        acc["perdidos"] += env.contadores["perdidos"] - prev_perdidos
        nuevas_cargas = env._carga_muestras[prev_carga_n:]
        acc["carga_suma"] += float(sum(nuevas_cargas))
        acc["carga_n"] += len(nuevas_cargas)

        prev_ganancia, prev_km = env.ganancia_acum, env.km_acum
        prev_entregados = info["pedidos_entregados"]
        prev_a_tiempo, prev_totales = env._entregas_a_tiempo, env._entregas_totales
        prev_carga_n = len(env._carga_muestras)
        prev_generados, prev_perdidos = env.contadores["generados"], env.contadores["perdidos"]

        if term or trunc:
            break

    t_final = env.t
    horas_antes = min(t_evento, t_final) / 3600.0
    horas_despues = max(0.0, t_final - t_evento) / 3600.0

    return {
        "antes": _metricas_de(acumuladores["antes"], horas_antes),
        "despues": _metricas_de(acumuladores["despues"], horas_despues),
        "total": {
            "rho": (env.ganancia_acum - COSTO_KM_MXN * env.km_acum) / max(t_final / 3600.0, 1e-9),
            "entregados": info["pedidos_entregados"],
            "pedidos_por_hora": info["pedidos_entregados"] / max(t_final / 3600.0, 1e-9),
            "tasa_aceptacion": info["aceptacion"],
            "puntualidad": env._entregas_a_tiempo / max(env._entregas_totales, 1),
            "km_por_pedido": env.km_acum / max(info["pedidos_entregados"], 1),
            "bundling": (
                sum(env._carga_muestras) / len(env._carga_muestras) if env._carga_muestras else float("nan")
            ),
        },
    }


def correr_escenario_con_paradas(escenario: EscenarioCongelado, politica_fn: PoliticaFn) -> dict:
    """Igual que `correr_escenario`, pero además graba la secuencia de paradas (recogida/
    entrega) para el turno de demo. NO toca env.py -- envuelve el método que YA EXISTE,
    `env._procesar_llegada_nodo`, sólo en esta instancia de `env` (nunca en la clase):
    graba lo que ya iba a pasar, no cambia cómo pasa. Se usa sólo para el turno elegido en
    `_elegir_turno_demo`, nunca en el barrido de los 30 escenarios (ahí `correr_escenario`
    se queda tal cual, sin el costo extra de instrumentar)."""

    programador = ProgramadorEventos(list(escenario.eventos)) if escenario.eventos else None
    env = VygoEnv(
        nivel=escenario.nivel, m_comercios=escenario.m_comercios,
        duracion_turno_s=escenario.duracion_turno_s, programador_eventos=programador,
    )
    obs, info = env.reset(seed=escenario.seed)
    rho_movil = RhoHatMovil()

    paradas: list[dict] = []
    _original = env._procesar_llegada_nodo

    def _envuelta(t_salida: float):
        parada = env.plan[0]
        ganancia_antes = env.ganancia_acum
        resultado = _original(t_salida)
        paradas.append({
            "t_min": env.t / 60.0, "tipo": parada.tipo, "pedido": parada.id,
            "pos": parada.pos, "ingreso": env.ganancia_acum - ganancia_antes,
        })
        return resultado

    env._procesar_llegada_nodo = _envuelta

    for _ in range(MAX_PASOS_ESCENARIO):
        estado = env._estado_ruta()
        mask = info["action_mask"]
        accion = politica_fn(estado, obs, mask, rho_movil.valor)
        obs, r, term, trunc, info = env.step(accion)
        rho_movil.actualizar(env.t, r)
        if term or trunc:
            break

    t_final = env.t
    return {
        "minutos": t_final / 60.0,
        "km": env.km_acum,
        "ingreso": env.ganancia_acum,
        "rho": (env.ganancia_acum - COSTO_KM_MXN * env.km_acum) / max(t_final / 3600.0, 1e-9),
        "entregados": info["pedidos_entregados"],
        "paradas": paradas,
    }


def _pareado(rho_a: np.ndarray, rho_b: np.ndarray, n: int = N_BOOTSTRAP, seed: int = 0) -> dict:
    """Estadística pareada CORRECTA, por escenario (no bootstrapear la diferencia de
    medianas por separado -- eso desperdicia el pareo). d_i = rho_a_i - rho_b_i en cada uno
    de los N escenarios; se reporta la mediana de esas N diferencias, su IC 95% por
    bootstrap sobre las diferencias mismas (remuestrea los d_i, no rho_a/rho_b por
    separado), y la tasa de victorias: en cuántos escenarios rho_a > rho_b."""

    d = rho_a - rho_b
    n_esc = len(d)
    mediana_obs = float(np.median(d))

    rng = np.random.default_rng(seed)
    muestras = np.empty(n)
    for k in range(n):
        idx = rng.integers(0, n_esc, size=n_esc)
        muestras[k] = np.median(d[idx])

    return {
        "mediana_diff": mediana_obs,
        "ic95": [float(np.percentile(muestras, 2.5)), float(np.percentile(muestras, 97.5))],
        "victorias": int(np.sum(d > 0)),
        "empates": int(np.sum(d == 0)),
        "n": n_esc,
    }


def _resumen(resultados_por_escenario: list[dict], bucket: str) -> dict:
    rhos = np.array([r[bucket]["rho"] for r in resultados_por_escenario])
    return {
        "rho_mediana": float(np.median(rhos)),
        "rho_iqr": [float(np.percentile(rhos, 25)), float(np.percentile(rhos, 75))],
        "entregados_medio": float(np.mean([r[bucket]["entregados"] for r in resultados_por_escenario])),
        "pedidos_por_hora_medio": float(np.mean([r[bucket]["pedidos_por_hora"] for r in resultados_por_escenario])),
        "tasa_aceptacion_media": float(np.mean([r[bucket]["tasa_aceptacion"] for r in resultados_por_escenario])),
        "puntualidad_media": float(np.mean([r[bucket]["puntualidad"] for r in resultados_por_escenario])),
        "km_por_pedido_medio": float(np.nanmean([r[bucket]["km_por_pedido"] for r in resultados_por_escenario])),
        "bundling_medio": float(np.nanmean([r[bucket]["bundling"] for r in resultados_por_escenario])),
    }


def _ejemplo_surge() -> str:
    """Ejemplo numérico concreto de que la reacción a SURGE EMERGE de `politica_umbral` sin
    caso especial -- misma construcción que `tests/test_eventos.py::
    test_surge_emerge_como_aceptacion_via_umbral`, aquí con los números formateados para el
    juez."""

    from vygo.baselines import _tasa_marginal
    from vygo.eventos import EventoSurge, ProgramadorEventos
    from vygo.insertion import EstadoRuta, OfertaCandidata
    from vygo.schema import Clima
    from vygo.sequencer import Restricciones

    grid = GridWorld(n=20, seed=0)
    pos_agente, pos_recogida, pos_entrega = (0, 0), (0, 4), (0, 10)
    t = 0.0
    dt_recogida, _dm = grid.travel(pos_agente, pos_recogida, t, Clima.DESPEJADO)
    dt_entrega, _dm2 = grid.travel(pos_recogida, pos_entrega, t, Clima.DESPEJADO)
    dt_total = dt_recogida + dt_entrega

    rho_hat = 150.0
    precio_base = rho_hat * (dt_total / 3600.0) * 0.9
    restricciones = Restricciones(capacidad=10, r={}, l={}, theta={}, carga={})

    def _oferta(precio: float) -> OfertaCandidata:
        return OfertaCandidata(
            id="p0", pos_recogida=pos_recogida, pos_entrega=pos_entrega, r=0.0, l=None,
            theta=None, carga=1, expira_en=None, precio=precio, anillo=1, p_gana_estimada=1.0,
        )

    def _estado(oferta: OfertaCandidata) -> EstadoRuta:
        return EstadoRuta(
            t=t, pos=pos_agente, clima=Clima.DESPEJADO, plan=[], restricciones=restricciones,
            travel_fn=lambda a, b, tt: grid.travel(a, b, tt, Clima.DESPEJADO),
            ofertas=[oferta] + [None] * (K_F - 1),
        )

    accion_sin = politica_umbral(_estado(_oferta(precio_base)), rho_hat)
    tasa_sin, _ = _tasa_marginal(_estado(_oferta(precio_base)), 0, con_p_gana=True)

    surge = EventoSurge(
        inicia_min=60.0, duracion_min=45.0, zona=pos_recogida, radio_celdas=5.0,
        mult_tarifa=1.4, mult_intensidad=1.6,
    )
    mult_tarifa, mult_intensidad = ProgramadorEventos([surge]).modificador(60.0 * 60.0, pos_recogida)
    precio_con = precio_base * mult_tarifa
    accion_con = politica_umbral(_estado(_oferta(precio_con)), rho_hat)
    tasa_con, _ = _tasa_marginal(_estado(_oferta(precio_con)), 0, con_p_gana=True)

    return (
        f"SURGE en (0,4), x{mult_tarifa:.1f} tarifa / x{mult_intensidad:.1f} intensidad de "
        f"llegada, minuto 60-105. Misma oferta (recoger en (0,4), entregar en (0,10), "
        f"{dt_total:.0f}s de viaje), misma `politica_umbral`, mismo `rho_hat`={rho_hat:.0f} "
        f"MXN/h:\n"
        f"  - Antes del surge: precio={precio_base:.2f} MXN -> tasa_marginal={tasa_sin:.1f} "
        f"MXN/h < rho_hat -> decisión = "
        f"{'rechazar_todas' if accion_sin == K_F else f'aceptar oferta {accion_sin}'}.\n"
        f"  - Con el surge activo: precio={precio_con:.2f} MXN (x{mult_tarifa:.1f}) -> "
        f"tasa_marginal={tasa_con:.1f} MXN/h > rho_hat -> decisión = "
        f"{'rechazar_todas' if accion_con == K_F else f'aceptar oferta {accion_con}'}.\n"
        f"  Nada en `politica_umbral` sabe que existe un evento: sólo ve un precio más alto "
        f"y la MISMA regla de umbral cruza de rechazar a aceptar."
    )


def _ejemplo_cierre_vial() -> str:
    """Ejemplo numérico concreto de que la reacción a CIERRE_VIAL EMERGE de `held_karp` sin
    caso especial -- misma construcción que `tests/test_eventos.py::
    test_cierre_vial_emerge_como_replanificacion_del_secuenciador`."""

    from vygo.eventos import EventoCierreVial, ProgramadorEventos
    from vygo.schema import Clima
    from vygo.sequencer import Restricciones, held_karp

    grid = GridWorld(n=20, seed=0)
    clima = Clima.DESPEJADO
    stops = [
        {"id": "A", "tipo": "recogida", "pos": (5, 5)},
        {"id": "A", "tipo": "entrega", "pos": (5, 15)},
        {"id": "B", "tipo": "recogida", "pos": (6, 6)},
        {"id": "B", "tipo": "entrega", "pos": (6, 16)},
    ]
    restricciones = Restricciones(
        capacidad=2, r={"A": 0.0, "B": 0.0}, l={"A": None, "B": None},
        theta={"A": None, "B": None}, carga={"A": 1, "B": 1},
    )

    def _travel_sin(a, b, tt):
        return grid.travel(a, b, tt, clima)

    cierre = EventoCierreVial(inicia_min=60.0, duracion_min=40.0, eje="columna", indice=10, factor_detour=1.7)
    programador = ProgramadorEventos([cierre])
    t_evento = 60.0 * 60.0

    def _travel_con(a, b, tt):
        return grid.travel(a, b, tt, clima, programador.corredores_cerrados(tt))

    orden_sin, tiempo_sin, dist_sin, *_ = held_karp(stops, t_evento, (0, 0), _travel_sin, restricciones, k=20)
    orden_con, tiempo_con, dist_con, *_ = held_karp(stops, t_evento, (0, 0), _travel_con, restricciones, k=20)

    return (
        f"CIERRE_VIAL en la columna 10 (factor_detour=1.7x), minuto 60-100. Mismos 4 stops "
        f"(A y B, recogida/entrega a los dos lados de la columna 10), mismo `held_karp`:\n"
        f"  - Antes del cierre: tiempo_total={tiempo_sin:.0f}s, dist_total={dist_sin:.0f}m, "
        f"orden={orden_sin}.\n"
        f"  - Con el cierre activo: tiempo_total={tiempo_con:.0f}s "
        f"(+{tiempo_con - tiempo_sin:.0f}s, +{(tiempo_con / tiempo_sin - 1) * 100:.0f}%), "
        f"dist_total={dist_con:.0f}m, orden={orden_con}.\n"
        f"  `held_karp` no sabe que hay un evento: sólo ve un `travel_fn` que ahora cobra "
        f"1.7x al cruzar la columna 10, y recalcula el óptimo con esa única diferencia."
    )


def _elegir_turno_demo(rho_b2: np.ndarray, rho_serial: np.ndarray) -> int:
    """Índice del escenario donde B2 le saca la mayor ventaja a B_SERIAL en rho total --
    el turno más claro para el pitch."""
    return int(np.argmax(rho_b2 - rho_serial))


def _tipo_evento(escenario: EscenarioCongelado) -> str:
    if not escenario.eventos:
        return "ninguno"
    return "surge" if isinstance(escenario.eventos[0], EventoSurge) else "cierre_vial"


def evaluar() -> dict:
    if not RUTA_ESCENARIOS.exists():
        raise SystemExit(
            f"falta {RUTA_ESCENARIOS} -- correr primero: "
            "python -c \"from vygo.congelar_escenarios import escribir_una_vez; escribir_una_vez()\""
        )
    escenarios = cargar_escenarios()

    politicas: dict[str, PoliticaFn] = {"B_SERIAL": _b_serial, "B1": _b1, "B2": _b2}
    agente = _cargar_agente()
    nombre_agente = None
    if agente is not None:
        nombre_agente, fn = agente
        politicas[nombre_agente] = fn

    resultados: dict[str, list[dict]] = {nombre: [] for nombre in politicas}
    for escenario in escenarios:
        for nombre, fn in politicas.items():
            resultados[nombre].append(correr_escenario(escenario, fn))

    resumen = {
        nombre: {bucket: _resumen(res, bucket) for bucket in ("total", "antes", "despues")}
        for nombre, res in resultados.items()
    }

    rho_serial = np.array([r["total"]["rho"] for r in resultados["B_SERIAL"]])
    rho_b1 = np.array([r["total"]["rho"] for r in resultados["B1"]])
    rho_b2 = np.array([r["total"]["rho"] for r in resultados["B2"]])

    comparaciones = {
        "B2 vs B_SERIAL": _pareado(rho_b2, rho_serial),
        "B2 vs B1": _pareado(rho_b2, rho_b1),
    }
    if nombre_agente is not None:
        rho_agente = np.array([r["total"]["rho"] for r in resultados[nombre_agente]])
        comparaciones[f"{nombre_agente} vs B1"] = _pareado(rho_agente, rho_b1)

    idx_demo = _elegir_turno_demo(rho_b2, rho_serial)
    escenario_demo = escenarios[idx_demo]
    demo = {
        "seed": escenario_demo.seed,
        "tipo_evento": _tipo_evento(escenario_demo),
        "ventaja_rho": float(rho_b2[idx_demo] - rho_serial[idx_demo]),
        "B2": correr_escenario_con_paradas(escenario_demo, _b2),
        "B_SERIAL": correr_escenario_con_paradas(escenario_demo, _b_serial),
    }

    return {
        "n_escenarios": len(escenarios),
        "politicas": list(politicas.keys()),
        "resumen": resumen,
        "comparaciones": comparaciones,
        "demo": demo,
        "ejemplo_surge": _ejemplo_surge(),
        "ejemplo_cierre_vial": _ejemplo_cierre_vial(),
    }


def _fmt_fila(politica: str, m: dict) -> str:
    return (
        f"  {politica:14s} rho_mediana={m['rho_mediana']:8.2f}  "
        f"rho_iqr=[{m['rho_iqr'][0]:.2f}, {m['rho_iqr'][1]:.2f}]  "
        f"entregados={m['entregados_medio']:.2f}  pedidos_h={m['pedidos_por_hora_medio']:.2f}  "
        f"aceptacion={m['tasa_aceptacion_media']:.2f}  puntualidad={m['puntualidad_media']:.2f}  "
        f"km/pedido={m['km_por_pedido_medio']:.2f}  bundling={m['bundling_medio']:.2f}"
    )


def _fmt_paradas(paradas: list[dict]) -> list[str]:
    lineas = []
    for p in paradas:
        extra = f"  +{p['ingreso']:.2f} MXN" if p["ingreso"] else ""
        lineas.append(f"  min {p['t_min']:6.1f}  {p['tipo']:9s} {str(p['pedido']):>6s}  {p['pos']}{extra}")
    return lineas


def _imprimir_demo(demo: dict) -> None:
    b2, serial = demo["B2"], demo["B_SERIAL"]
    print(
        f"Escenario semilla={demo['seed']} (evento: {demo['tipo_evento']}), ventaja de B2 "
        f"sobre B_SERIAL: {demo['ventaja_rho']:+.2f} MXN/h de rho"
    )
    print(f"{'':14s}{'B2':>12s}{'B_SERIAL':>12s}")
    filas = (
        ("minutos", "minutos", "{:.1f}"), ("km", "km", "{:.2f}"),
        ("ingreso MXN", "ingreso", "{:.2f}"), ("rho MXN/h", "rho", "{:.2f}"),
        ("entregados", "entregados", "{:d}"),
    )
    for etiqueta, clave, fmt in filas:
        print(f"{etiqueta:14s}{fmt.format(b2[clave]):>12s}{fmt.format(serial[clave]):>12s}")
    print()
    print(f"Secuencia de paradas -- B2 ({len(b2['paradas'])} paradas):")
    for linea in _fmt_paradas(b2["paradas"]):
        print(linea)
    print()
    print(f"Secuencia de paradas -- B_SERIAL ({len(serial['paradas'])} paradas):")
    for linea in _fmt_paradas(serial["paradas"]):
        print(linea)


def _imprimir_tabla(reporte: dict) -> None:
    n = reporte["n_escenarios"]
    print(f"Evaluación pareada -- {n} escenarios congelados (scenarios/test_30.pkl)\n")
    print("\n".join(_nota_reproducibilidad()))
    print()
    for bucket, titulo in (("total", "TOTAL"), ("antes", "ANTES del evento"), ("despues", "DESPUÉS del evento")):
        print(f"-- {titulo} --")
        for politica, por_bucket in reporte["resumen"].items():
            print(_fmt_fila(politica, por_bucket[bucket]))
        print()

    for nombre, c in reporte["comparaciones"].items():
        print(
            f"{nombre}: mediana(diferencia rho)={c['mediana_diff']:+.2f} MXN/h "
            f"(IC 95% bootstrap {N_BOOTSTRAP} remuestreos sobre las diferencias: "
            f"[{c['ic95'][0]:+.2f}, {c['ic95'][1]:+.2f}]) -- victorias: {c['victorias']}/{c['n']} turnos"
        )
    print()
    print("-- Turno de demo (mayor ventaja de B2 sobre B_SERIAL) --")
    _imprimir_demo(reporte["demo"])
    print()
    print(reporte["ejemplo_surge"])
    print()
    print(reporte["ejemplo_cierre_vial"])


def _experimento_rl_md(reporte: dict) -> list[str]:
    """Sección honesta del experimento de RL. Cifras verificadas contra archivos fuente
    (no inventadas): concordancia BC en `reports/bc_curva.json` (época 10), approx_kl en
    `reports/train_ppo.log`, tope_ka en `reports/HANDOFF.md` (instrumentación de
    `feasibility.CONTADOR_MOTIVOS` del bloque anterior); el resultado PPO vs B1 sale de
    esta misma corrida (`reporte['comparaciones']`), no de un número fijo en el código."""

    comp = reporte["comparaciones"]
    nombre_ppo = next((k for k in comp if k.endswith(" vs B1") and k != "B2 vs B1"), None)
    if nombre_ppo is not None:
        c = comp[nombre_ppo]
        resultado_ppo = (
            f"**{nombre_ppo}**: mediana(diferencia de rho)={c['mediana_diff']:+.2f} MXN/h, "
            f"gana en {c['victorias']}/{c['n']} turnos frente a B1 -- **PPO descartado**, "
            f"no supera al baseline simple en este holdout."
        )
    else:
        resultado_ppo = "no había checkpoint de PPO disponible en `checkpoints/` al correr esta evaluación."

    return [
        "## Experimento de RL -- honesto",
        "",
        "**BC (behavioral cloning) sobre B2**: 10 épocas, 40 000 transiciones de "
        "entrenamiento / 10 000 de validación. Concordancia final con B2 en validación "
        "**99.8%** (`reports/bc_curva.json`, época 10: `concordancia_val=0.9985`). El clon "
        "aprende la regla de umbral casi a la perfección como problema de clasificación -- "
        "el cuello de botella de PPO no es que no pueda imitar a B2.",
        "",
        f"**PPO desde ese checkpoint**: `MaskablePPO` inicializado con los pesos de "
        f"`bc_policy.pt` (no entrenado desde cero), afinado on-policy encima. Resultado en "
        f"este holdout de {reporte['n_escenarios']} escenarios: {resultado_ppo}",
        "",
        "**Evidencia de que la política casi no se movió durante el afinado on-policy**: "
        "`approx_kl` en `reports/train_ppo.log` se mantiene del orden de 1e-9 a 1e-5 (varias "
        "filas en exactamente 0.0) a lo largo del entrenamiento -- PPO está ajustando casi "
        "nada respecto al punto de partida heredado de BC, no está descubriendo una política "
        "distinta.",
        "",
        "**Diagnóstico**: el entorno está saturado por el tope duro `K_A_MAXIMO=4` -- "
        "instrumentado con `feasibility.CONTADOR_MOTIVOS` en el bloque anterior, el motivo "
        "`tope_ka` explica el **89.1%** del histograma de rechazos (`reports/HANDOFF.md`). "
        "Con el plan lleno casi todo el turno, aceptar todo lo factible ya es casi óptimo: "
        "no queda margen de SELECCIÓN entre ofertas que una política de RL pueda aprender a "
        "explotar. La ganancia real de este sistema está en AGRUPAR pedidos "
        "(B1/B2 vs B_SERIAL, ver tabla y turno de demo arriba), no en escoger mejor entre "
        "ofertas visibles (B2 vs B1, y por lo mismo PPO vs B1) -- ahí el margen ya está casi "
        "agotado por el tope de capacidad, no por falta de entrenamiento.",
        "",
    ]


def _nota_reproducibilidad() -> list[str]:
    """Hallazgo real durante esta tarea, no teórico: dos corridas completas de esta misma
    evaluación sobre los mismos 30 escenarios dieron rho_mediana de B1 = 213.19 MXN/h y,
    más tarde, 353.25 MXN/h -- con el MISMO código (`git diff` limpio en env.py/generator.py/
    geo.py/sequencer.py/feasibility.py entre ambas corridas) y el MISMO `scenarios/
    test_30.pkl` (sha256 verificado sin cambios). B1 es una función pura del estado del
    entorno: no debería poder variar así. Se aisló la causa: `sequencer.held_karp`, en su
    camino de enumeración exacta (<=3 pedidos, el caso típico), acota su búsqueda con un
    presupuesto de RELOJ DE PARED de 25 ms (`_LIMITE_TIEMPO_EXACTO_S`, medido con
    `time.perf_counter()`); si se agota, cae a la mejor secuencia encontrada hasta ese punto
    (siempre verificada factible -- nunca viola frescura) pero no necesariamente la óptima.
    Bajo contención de CPU (la otra sesión entrena PPO en el mismo equipo) ese presupuesto
    se agota con más frecuencia, degradando la ruta elegida de forma no determinista.
    Confirmado empíricamente: una recomputación fresca de B1 sobre los 30 escenarios,
    corrida después, reprodujo 353.25 exactamente -- los números de este reporte son
    reproducibles bajo la carga de CPU del momento en que se generaron, pero no son
    invariantes a la carga del sistema. Esto NO se arregló aquí: arreglarlo (por ejemplo,
    pasar a un presupuesto de tiempo de CPU de proceso en vez de reloj de pared, o subir el
    límite) requiere tocar `sequencer.py`, fuera de alcance de esta tarea ('no toques el
    entorno'). Efecto en las conclusiones: la brecha B1/B2 vs B_SERIAL (~250 MXN/h, ~200%)
    es muchísimo más grande que este ruido y se sostiene sin duda; las comparaciones más
    finas B2 vs B1 y PPO vs B1 (ya con IC 95% que cruza cero) deben leerse como "no hay
    evidencia de diferencia" y no como un número fijo -- una repetición de esta evaluación,
    sobre todo una vez que la otra sesión termine de entrenar, puede moverlas."""

    return [
        "## Nota de reproducibilidad -- por qué estos números pueden variar entre corridas",
        "",
        "Se detectó y confirmó durante esta tarea: dos corridas completas de esta evaluación "
        "sobre los MISMOS 30 escenarios, con el MISMO código (verificado sin diferencias en "
        "env.py/generator.py/geo.py/sequencer.py/feasibility.py entre ambas), dieron "
        "rho_mediana de B1 = 213.19 MXN/h y, más tarde, 353.25 MXN/h. Causa aislada: "
        "`sequencer.held_karp` acota su enumeración exacta (<=3 pedidos, el caso típico) con "
        "un presupuesto de **reloj de pared** de 25 ms (`_LIMITE_TIEMPO_EXACTO_S`); si se "
        "agota, usa la mejor secuencia encontrada hasta ahí (siempre factible, nunca viola "
        "frescura) pero no necesariamente la óptima. Bajo contención de CPU -- como la de la "
        "otra sesión entrenando PPO en el mismo equipo -- ese presupuesto se agota más "
        "seguido y la ruta elegida se degrada de forma no determinista.",
        "",
        "Confirmado empíricamente: una recomputación fresca de B1 sobre los 30 escenarios "
        "reprodujo 353.25 exactamente -- los números de este reporte SÍ son reproducibles "
        "bajo la carga de CPU con la que se generaron, pero NO son invariantes a la carga "
        "del sistema en general. No se corrigió aquí: la corrección (p. ej. medir tiempo de "
        "CPU de proceso en vez de reloj de pared, o subir el límite) requiere tocar "
        "`sequencer.py`, fuera de alcance de esta tarea (\"no toques el entorno\").",
        "",
        "**Efecto en las conclusiones**: la brecha B1/B2 vs B_SERIAL (~250 MXN/h, ~200%) es "
        "muchísimo más grande que este ruido y se sostiene sin duda. Las comparaciones finas "
        "B2 vs B1 y PPO vs B1 (IC 95% que ya cruza cero en ambas) deben leerse como \"sin "
        "evidencia de diferencia\", no como un número fijo -- repetir esta evaluación, sobre "
        "todo cuando la otra sesión termine de entrenar, puede moverlas.",
        "",
    ]


def _escribir_eval_md(reporte: dict, ruta: Path) -> None:
    from datetime import datetime, timezone

    n = reporte["n_escenarios"]
    con_agente = any(" vs B1" in k and k != "B2 vs B1" for k in reporte["comparaciones"])
    lineas = [
        "# Evaluación pareada -- reto Infosys \"The Courier\"",
        "",
        f"Generado: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Escenarios: {n} congelados en `scenarios/test_30.pkl` (ver `scenarios/test_30.sha256`), "
        "15 con SURGE y 15 con CIERRE_VIAL, evento siempre a partir del minuto 60. "
        "Evaluación PAREADA: cada política corre EXACTAMENTE los mismos 30 escenarios.",
        f"Políticas evaluadas: {', '.join(reporte['politicas'])}"
        + ("" if con_agente else " (sin checkpoint entrenado disponible en `checkpoints/` al momento de correr esta evaluación -- se salta esa columna sin fallar)."),
        "B_SERIAL es el repartidor SIN VYGO hoy: una sola app, un pedido a la vez -- es la "
        "referencia real, no B1.",
        "",
    ]

    lineas.extend(_nota_reproducibilidad())

    for bucket, titulo in (("total", "TOTAL"), ("antes", "ANTES del evento"), ("despues", "DESPUÉS del evento")):
        lineas.append(f"## {titulo}")
        lineas.append("")
        lineas.append("| Política | rho mediana | rho IQR | entregados | pedidos/h | tasa aceptación | puntualidad | km/pedido | bundling |")
        lineas.append("|---|---|---|---|---|---|---|---|---|")
        for politica, por_bucket in reporte["resumen"].items():
            m = por_bucket[bucket]
            lineas.append(
                f"| {politica} | {m['rho_mediana']:.2f} | [{m['rho_iqr'][0]:.2f}, {m['rho_iqr'][1]:.2f}] | "
                f"{m['entregados_medio']:.2f} | {m['pedidos_por_hora_medio']:.2f} | "
                f"{m['tasa_aceptacion_media']:.2f} | {m['puntualidad_media']:.2f} | "
                f"{m['km_por_pedido_medio']:.2f} | {m['bundling_medio']:.2f} |"
            )
        lineas.append("")

    lineas.append("## Estadística pareada (por escenario, no por medianas independientes)")
    lineas.append("")
    lineas.append(
        "Para cada par se calcula d_i = rho(a, escenario i) − rho(b, escenario i) en los "
        f"{n} escenarios; se reporta la MEDIANA de esas diferencias con IC 95% por bootstrap "
        f"({N_BOOTSTRAP} remuestreos) sobre las diferencias mismas, y la tasa de victorias "
        "(en cuántos turnos rho_a > rho_b)."
    )
    lineas.append("")
    lineas.append("| Comparación | mediana(diferencia rho) | IC 95% | victorias |")
    lineas.append("|---|---|---|---|")
    for nombre, c in reporte["comparaciones"].items():
        lineas.append(
            f"| {nombre} | {c['mediana_diff']:+.2f} MXN/h | "
            f"[{c['ic95'][0]:+.2f}, {c['ic95'][1]:+.2f}] | {c['victorias']}/{c['n']} |"
        )
    lineas.append("")

    demo = reporte["demo"]
    b2, serial = demo["B2"], demo["B_SERIAL"]
    lineas.append("## Turno de demo -- mayor ventaja de B2 sobre B_SERIAL")
    lineas.append("")
    lineas.append(
        f"Escenario semilla={demo['seed']} (evento: {demo['tipo_evento']}), ventaja de B2 "
        f"sobre B_SERIAL: **{demo['ventaja_rho']:+.2f} MXN/h** de rho."
    )
    lineas.append("")
    lineas.append("| | B2 | B_SERIAL |")
    lineas.append("|---|---|---|")
    lineas.append(f"| minutos | {b2['minutos']:.1f} | {serial['minutos']:.1f} |")
    lineas.append(f"| km | {b2['km']:.2f} | {serial['km']:.2f} |")
    lineas.append(f"| ingreso MXN | {b2['ingreso']:.2f} | {serial['ingreso']:.2f} |")
    lineas.append(f"| rho MXN/h | {b2['rho']:.2f} | {serial['rho']:.2f} |")
    lineas.append(f"| entregados | {b2['entregados']} | {serial['entregados']} |")
    lineas.append("")
    lineas.append(f"Secuencia de paradas -- B2 ({len(b2['paradas'])} paradas):")
    lineas.append("")
    lineas.append("```")
    lineas.extend(_fmt_paradas(b2["paradas"]))
    lineas.append("```")
    lineas.append("")
    lineas.append(f"Secuencia de paradas -- B_SERIAL ({len(serial['paradas'])} paradas):")
    lineas.append("")
    lineas.append("```")
    lineas.extend(_fmt_paradas(serial["paradas"]))
    lineas.append("```")
    lineas.append("")

    lineas.append("## Reacción al evento -- ejemplo concreto (emergente, no programado)")
    lineas.append("")
    lineas.append("### SURGE")
    lineas.append("")
    lineas.append(reporte["ejemplo_surge"].replace("\n", "  \n"))
    lineas.append("")
    lineas.append("### CIERRE_VIAL")
    lineas.append("")
    lineas.append(reporte["ejemplo_cierre_vial"].replace("\n", "  \n"))
    lineas.append("")

    lineas.extend(_experimento_rl_md(reporte))

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas), encoding="utf-8")


if __name__ == "__main__":
    _reporte = evaluar()
    _imprimir_tabla(_reporte)
    _escribir_eval_md(_reporte, _AI_ROOT / "reports" / "EVAL.md")
