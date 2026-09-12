"""Genera `demo/turno_datos.json` (embebido luego en `demo/turno.html`, ver
`vygo/empaquetar_demo.py`): un turno CONGELADO de `scenarios/test_30.pkl`, corrido con B1 y
B2 lado a lado (mismo escenario, mismo evento de media jornada) y, si existe un checkpoint
entrenado, un tercer replay "agente". Cada replay es una lista de FRAMES dispersos -- sólo
en los instantes en que algo visible cambia (posición, ganancia, composición del plan,
evento) o el agente toma una decisión real de aceptar/rechazar, no un frame por cada
cierre de ronda trivial -- para que el HTML no tenga que cargar decenas de miles de puntos
que no aportan nada a la animación.

Uso: python -m vygo.generar_demo [--escenario N]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Optional

from vygo.baselines import COSTO_KM_MXN, RhoHatMovil, _tasa_marginal, politica_primera_factible, politica_umbral
from vygo.congelar_escenarios import EscenarioCongelado, cargar_escenarios
from vygo.env import VygoEnv
from vygo.eventos import EventoCierreVial, EventoSurge, ProgramadorEventos
from vygo.feasibility import K_F
from vygo.insertion import EstadoRuta, eval_insertion

_AI_ROOT = Path(__file__).resolve().parent.parent
RUTA_DATOS = _AI_ROOT / "demo" / "turno_datos.json"
MAX_PASOS = 20_000


def _mejor_candidata(estado: EstadoRuta, mask, rho_hat: float) -> Optional[tuple[int, float]]:
    mejor_i, mejor_tasa = None, -math.inf
    for i in range(K_F):
        if not mask[i]:
            continue
        tasa, ok = _tasa_marginal(estado, i, con_p_gana=True)
        if ok and tasa > mejor_tasa:
            mejor_tasa, mejor_i = tasa, i
    if mejor_i is None:
        return None
    return mejor_i, mejor_tasa


def _decision_de(estado: EstadoRuta, mask, accion: int, rho_hat: float) -> Optional[dict]:
    candidata = _mejor_candidata(estado, mask, rho_hat)
    if candidata is None:
        return None
    i, tasa = candidata
    oferta = estado.ofertas[i]
    dt_s, dd_m, factible = eval_insertion(estado.plan, oferta, estado)
    if not factible:
        return None
    aceptada = accion == i
    verbo = "Aceptado" if aceptada else "Rechazado"
    return {
        "oferta_id": oferta.id,
        "accion": "aceptado" if aceptada else "rechazado",
        "tasa_marginal": round(tasa, 1),
        "rho_hat": round(rho_hat, 1),
        "delta_min": round(dt_s / 60.0, 1),
        "delta_km": round(dd_m / 1000.0, 2),
        "holgura_frescura_min": round((oferta.theta or 0.0) / 60.0, 1) if oferta.theta else None,
        "frase": f"{verbo}: te paga a ${tasa:.0f}/h, tu promedio hoy es ${rho_hat:.0f}/h.",
    }


def _plan_a_bordo(env: VygoEnv) -> list[dict]:
    ids_por_recoger = {p.id for p in env.plan if p.tipo == "recogida"}
    vistos: set[str] = set()
    items = []
    for parada in env.plan:
        if parada.id in vistos or parada.id in ids_por_recoger:
            continue
        vistos.add(parada.id)
        p = env.pedidos[parada.id]
        l = env.restricciones.l.get(parada.id)
        holgura_restante = (l - env.t) if l is not None else p.theta_frescura
        frac = max(0.0, min(1.0, holgura_restante / max(p.theta_frescura, 1e-6)))
        items.append({
            "id": parada.id,
            "origen": list(p.origen),
            "destino": list(p.destino),
            "frescura_frac": round(frac, 3),
        })
    return items


def _correr_replay(escenario: EscenarioCongelado, politica: str) -> list[dict]:
    programador = ProgramadorEventos(list(escenario.eventos)) if escenario.eventos else None
    env = VygoEnv(
        nivel=escenario.nivel, m_comercios=escenario.m_comercios,
        duracion_turno_s=escenario.duracion_turno_s, programador_eventos=programador,
    )
    obs, info = env.reset(seed=escenario.seed)
    rho_movil = RhoHatMovil()

    frames: list[dict] = []
    prev_pos = None
    prev_ganancia = None
    prev_plan_ids: Optional[frozenset] = None
    prev_evento = None

    for _ in range(MAX_PASOS):
        estado = env._estado_ruta()
        mask = info["action_mask"]
        if politica == "B1":
            accion = politica_primera_factible(estado)
        else:
            accion = politica_umbral(estado, rho_movil.valor, con_p_gana=True)

        decision = _decision_de(estado, mask, accion, rho_movil.valor)

        obs, r, term, trunc, info = env.step(accion)
        rho_movil.actualizar(env.t, r)

        plan_a_bordo = _plan_a_bordo(env)
        plan_ids = frozenset(item["id"] for item in plan_a_bordo)
        evento_tipo = programador.evento_activo_tipo(env.t) if programador else None

        cambio = (
            env.pos != prev_pos
            or env.ganancia_acum != prev_ganancia
            or plan_ids != prev_plan_ids
            or evento_tipo != prev_evento
            or decision is not None
        )
        if cambio:
            frames.append({
                "t": round(env.t, 1),
                "pos": list(env.pos),
                "ganancia": round(env.ganancia_acum, 2),
                "rho": round((env.ganancia_acum - COSTO_KM_MXN * env.km_acum) / max(env.t / 3600.0, 1e-9), 1),
                "plan": plan_a_bordo,
                "evento": evento_tipo,
                "decision": decision,
            })
            prev_pos, prev_ganancia, prev_plan_ids, prev_evento = env.pos, env.ganancia_acum, plan_ids, evento_tipo

        if term or trunc:
            break

    return frames


def _evento_a_dict(escenario: EscenarioCongelado) -> Optional[dict]:
    if not escenario.eventos:
        return None
    ev = escenario.eventos[0]
    if isinstance(ev, EventoSurge):
        return {
            "tipo": "surge", "inicia_s": ev.inicia_min * 60.0, "fin_s": ev.fin_min * 60.0,
            "zona": list(ev.zona), "radio_celdas": ev.radio_celdas,
            "mult_tarifa": ev.mult_tarifa, "mult_intensidad": ev.mult_intensidad,
        }
    if isinstance(ev, EventoCierreVial):
        return {
            "tipo": "cierre_vial", "inicia_s": ev.inicia_min * 60.0, "fin_s": ev.fin_min * 60.0,
            "eje": ev.eje, "indice": ev.indice, "factor_detour": ev.factor_detour,
        }
    return None


def generar(indice_escenario: int = 0) -> dict:
    escenarios = cargar_escenarios()
    escenario = escenarios[indice_escenario]

    grid_temporal = VygoEnv(nivel=escenario.nivel, m_comercios=escenario.m_comercios)
    grid_temporal.reset(seed=escenario.seed)
    comercios = [list(c.pos) for c in grid_temporal.generador.comercios]
    grid_n = grid_temporal.grid.n

    politicas = {"B1": _correr_replay(escenario, "B1"), "B2": _correr_replay(escenario, "B2")}

    from vygo.evaluate import _cargar_agente  # import perezoso, ver docstring del módulo

    agente = _cargar_agente()
    if agente is not None:
        nombre, fn = agente
        frames = []
        programador = ProgramadorEventos(list(escenario.eventos)) if escenario.eventos else None
        env = VygoEnv(
            nivel=escenario.nivel, m_comercios=escenario.m_comercios,
            duracion_turno_s=escenario.duracion_turno_s, programador_eventos=programador,
        )
        obs, info = env.reset(seed=escenario.seed)
        prev_pos = prev_ganancia = prev_plan_ids = prev_evento = None
        for _ in range(MAX_PASOS):
            estado = env._estado_ruta()
            mask = info["action_mask"]
            accion = fn(estado, obs, mask, 0.0)
            obs, r, term, trunc, info = env.step(accion)
            plan_a_bordo = _plan_a_bordo(env)
            plan_ids = frozenset(item["id"] for item in plan_a_bordo)
            evento_tipo = programador.evento_activo_tipo(env.t) if programador else None
            if (env.pos != prev_pos or env.ganancia_acum != prev_ganancia
                    or plan_ids != prev_plan_ids or evento_tipo != prev_evento):
                frames.append({
                    "t": round(env.t, 1), "pos": list(env.pos), "ganancia": round(env.ganancia_acum, 2),
                    "rho": round((env.ganancia_acum - COSTO_KM_MXN * env.km_acum) / max(env.t / 3600.0, 1e-9), 1),
                    "plan": plan_a_bordo, "evento": evento_tipo, "decision": None,
                })
                prev_pos, prev_ganancia, prev_plan_ids, prev_evento = env.pos, env.ganancia_acum, plan_ids, evento_tipo
            if term or trunc:
                break
        politicas[nombre] = frames

    datos = {
        "grid_n": grid_n,
        "duracion_s": escenario.duracion_turno_s,
        "comercios": comercios,
        "evento": _evento_a_dict(escenario),
        "politicas": politicas,
    }
    return datos


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--escenario", type=int, default=0)
    args = parser.parse_args()

    datos = generar(args.escenario)
    RUTA_DATOS.parent.mkdir(parents=True, exist_ok=True)
    RUTA_DATOS.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    n_frames = {k: len(v) for k, v in datos["politicas"].items()}
    print(f"escrito {RUTA_DATOS} -- frames por política: {n_frames}")
