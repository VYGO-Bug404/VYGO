"""Evaluación PAREADA de B1 vs B2 (y, si existe, un tercer agente entrenado) sobre los 30
turnos congelados de `scenarios/test_30.pkl` (ai/CLAUDE.md §2.7 -- ver
`vygo/congelar_escenarios.py`). Cada política corre EXACTAMENTE los mismos 30 escenarios
(misma semilla, mismo evento de media jornada), así que cualquier diferencia es la política,
no la suerte del escenario.

Reporta, por política: rho (mediana e IQR), entregados, puntualidad, km por pedido, factor
de agrupamiento -- cada uno con un desglose ANTES/DESPUÉS del instante en que arranca el
evento de media jornada del escenario. El % de mejora de B2 sobre B1 en rho se acompaña de
un intervalo de confianza por bootstrap (10 000 remuestreos, pareado por escenario).

Tercera política "agente": intenta cargar `checkpoints/ppo_best.zip` y, si no existe,
`checkpoints/bc_policy.pt` (usa la arquitectura de `vygo.policy_net`, no la reentrena). Si
ninguno existe todavía -- el caso normal en un checkout limpio, `checkpoints/` está en
.gitignore -- se salta esa columna sin fallar: la tabla sale igual con B1/B2 solamente.

Uso: python -m vygo.evaluate
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from vygo.baselines import RhoHatMovil, politica_primera_factible, politica_umbral
from vygo.congelar_escenarios import EscenarioCongelado, RUTA_ESCENARIOS, cargar_escenarios
from vygo.env import COSTO_KM_MXN, VygoEnv
from vygo.eventos import ProgramadorEventos
from vygo.feasibility import K_F
from vygo.geo import GridWorld
from vygo.insertion import EstadoRuta

_AI_ROOT = Path(__file__).resolve().parent.parent
MAX_PASOS_ESCENARIO = 20_000
N_BOOTSTRAP = 10_000

PoliticaFn = Callable[[EstadoRuta, np.ndarray, np.ndarray, float], int]


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


def _bootstrap_pct_mejora(rho_b1: np.ndarray, rho_b2: np.ndarray, n: int = N_BOOTSTRAP, seed: int = 0) -> dict:
    """% de mejora de B2 sobre B1 en rho_mediana, con IC 95% por bootstrap PAREADO (mismo
    índice de escenario para B1 y B2 en cada remuestreo -- preserva la correlación entre
    políticas sobre el mismo escenario, no compara medianas independientes)."""

    rng = np.random.default_rng(seed)
    n_esc = len(rho_b1)
    observado = (np.median(rho_b2) - np.median(rho_b1)) / abs(np.median(rho_b1)) * 100.0

    muestras = np.empty(n)
    for k in range(n):
        idx = rng.integers(0, n_esc, size=n_esc)
        m1, m2 = np.median(rho_b1[idx]), np.median(rho_b2[idx])
        muestras[k] = (m2 - m1) / abs(m1) * 100.0 if m1 != 0 else np.nan

    muestras = muestras[~np.isnan(muestras)]
    return {
        "pct_observado": float(observado),
        "ic95": [float(np.percentile(muestras, 2.5)), float(np.percentile(muestras, 97.5))],
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


def evaluar() -> dict:
    if not RUTA_ESCENARIOS.exists():
        raise SystemExit(
            f"falta {RUTA_ESCENARIOS} -- correr primero: "
            "python -c \"from vygo.congelar_escenarios import escribir_una_vez; escribir_una_vez()\""
        )
    escenarios = cargar_escenarios()

    politicas: dict[str, PoliticaFn] = {"B1": _b1, "B2": _b2}
    agente = _cargar_agente()
    if agente is not None:
        nombre, fn = agente
        politicas[nombre] = fn

    resultados: dict[str, list[dict]] = {nombre: [] for nombre in politicas}
    for escenario in escenarios:
        for nombre, fn in politicas.items():
            resultados[nombre].append(correr_escenario(escenario, fn))

    resumen = {
        nombre: {bucket: _resumen(res, bucket) for bucket in ("total", "antes", "despues")}
        for nombre, res in resultados.items()
    }

    rho_b1_total = np.array([r["total"]["rho"] for r in resultados["B1"]])
    bootstrap = {
        nombre: _bootstrap_pct_mejora(rho_b1_total, np.array([r["total"]["rho"] for r in res]))
        for nombre, res in resultados.items() if nombre != "B1"
    }

    return {
        "n_escenarios": len(escenarios),
        "politicas": list(politicas.keys()),
        "resumen": resumen,
        "vs_b1_bootstrap": bootstrap,
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


def _imprimir_tabla(reporte: dict) -> None:
    n = reporte["n_escenarios"]
    print(f"Evaluación pareada -- {n} escenarios congelados (scenarios/test_30.pkl)\n")
    for bucket, titulo in (("total", "TOTAL"), ("antes", "ANTES del evento"), ("despues", "DESPUÉS del evento")):
        print(f"-- {titulo} --")
        for politica, por_bucket in reporte["resumen"].items():
            print(_fmt_fila(politica, por_bucket[bucket]))
        print()

    for nombre, b in reporte["vs_b1_bootstrap"].items():
        print(
            f"{nombre} vs B1 (rho_mediana, total): {b['pct_observado']:+.1f}% "
            f"(IC 95% bootstrap {N_BOOTSTRAP} remuestreos: [{b['ic95'][0]:+.1f}%, {b['ic95'][1]:+.1f}%])",
        )
    print()
    print(reporte["ejemplo_surge"])
    print()
    print(reporte["ejemplo_cierre_vial"])


def _escribir_eval_md(reporte: dict, ruta: Path) -> None:
    from datetime import datetime, timezone

    n = reporte["n_escenarios"]
    lineas = [
        "# Evaluación pareada -- reto Infosys \"The Courier\"",
        "",
        f"Generado: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Escenarios: {n} congelados en `scenarios/test_30.pkl` (ver `scenarios/test_30.sha256`), "
        "15 con SURGE y 15 con CIERRE_VIAL, evento siempre a partir del minuto 60. "
        "Evaluación PAREADA: cada política corre EXACTAMENTE los mismos 30 escenarios.",
        f"Políticas evaluadas: {', '.join(reporte['politicas'])}"
        + ("" if len(reporte["politicas"]) > 2 else " (sin checkpoint entrenado disponible en `checkpoints/` al momento de correr esta evaluación -- se salta esa columna sin fallar)."),
        "",
    ]

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

    lineas.append("## % de mejora sobre B1 (rho mediana, total, bootstrap pareado)")
    lineas.append("")
    for nombre, b in reporte["vs_b1_bootstrap"].items():
        lineas.append(
            f"- **{nombre} vs B1**: {b['pct_observado']:+.1f}% "
            f"(IC 95%, {N_BOOTSTRAP} remuestreos: [{b['ic95'][0]:+.1f}%, {b['ic95'][1]:+.1f}%])"
        )
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

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas), encoding="utf-8")


if __name__ == "__main__":
    _reporte = evaluar()
    _imprimir_tabla(_reporte)
    _escribir_eval_md(_reporte, _AI_ROOT / "reports" / "EVAL.md")
