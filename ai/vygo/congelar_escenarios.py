"""Genera `scenarios/test_30.pkl` -- SE ESCRIBE UNA VEZ, nunca se regenera (ai/CLAUDE.md
§2.7: semillas de test separadas y congeladas para siempre, ni siquiera para elegir
hiperparámetros). 30 turnos de 2h, semillas 10000-10029 (rango reservado para
validación/test, nunca usado para entrenar -- ver vygo/bc.py), 15 con SURGE y 15 con
CIERRE_VIAL (vygo/eventos.py). L0 (sin competidores sintéticos, ver ai/CLAUDE.md/generator.py):
en L1 con m_comercios=80 el agente no gana NINGUNA ronda contra los 25 competidores
sintéticos en un turno de 2h (`entregados=0` verificado, seed 0, sin eventos de por medio --
hallazgo pre-existente de L1, no introducido por esta tarea), lo que vuelve cualquier
comparación B1 vs B2 ruido puro. L0 es la única forma de que esta evaluación mida algo real
hoy; queda documentado en reports/HANDOFF.md como pendiente de L1.

Uso: python -m vygo.congelar_escenarios     (falla si el archivo ya existe)
"""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import dataclass
from pathlib import Path

from vygo.eventos import Evento, EventoCierreVial, EventoSurge

_AI_ROOT = Path(__file__).resolve().parent.parent
RUTA_ESCENARIOS = _AI_ROOT / "scenarios" / "test_30.pkl"

N_ESCENARIOS = 30
SEMILLA_INICIO = 10_000
DURACION_TURNO_S = 2 * 3600.0
M_COMERCIOS = 80  # 4 zonas x 15 + 20 dispersos (generator.muestrear_comercios), congelado


@dataclass(frozen=True, slots=True)
class EscenarioCongelado:
    seed: int
    nivel: str
    m_comercios: int
    duracion_turno_s: float
    eventos: tuple[Evento, ...]


def _construir_escenarios() -> list[EscenarioCongelado]:
    escenarios = []
    for i in range(N_ESCENARIOS):
        seed = SEMILLA_INICIO + i
        if i < N_ESCENARIOS // 2:
            eventos = (EventoSurge(
                inicia_min=60.0, duracion_min=45.0, zona=(10, 10), radio_celdas=4.0,
                mult_tarifa=1.4, mult_intensidad=1.6,
            ),)
        else:
            eventos = (EventoCierreVial(
                inicia_min=60.0, duracion_min=40.0, eje="columna", indice=10, factor_detour=1.7,
            ),)
        escenarios.append(EscenarioCongelado(
            seed=seed, nivel="L0", m_comercios=M_COMERCIOS,
            duracion_turno_s=DURACION_TURNO_S, eventos=eventos,
        ))
    return escenarios


def escribir_una_vez() -> None:
    if RUTA_ESCENARIOS.exists():
        raise SystemExit(
            f"{RUTA_ESCENARIOS} ya existe -- es un holdout CONGELADO, no se regenera "
            "(ai/CLAUDE.md §2.7). Si de verdad hace falta cambiarlo, bórralo a mano primero "
            "y documenta por qué en reports/HANDOFF.md."
        )
    RUTA_ESCENARIOS.parent.mkdir(parents=True, exist_ok=True)
    escenarios = _construir_escenarios()
    with open(RUTA_ESCENARIOS, "wb") as f:
        pickle.dump(escenarios, f)
    print(f"escrito {RUTA_ESCENARIOS} ({len(escenarios)} escenarios)")


def hash_archivo(ruta: Path = RUTA_ESCENARIOS) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def cargar_escenarios(ruta: Path = RUTA_ESCENARIOS) -> list[EscenarioCongelado]:
    with open(ruta, "rb") as f:
        return pickle.load(f)


if __name__ == "__main__":
    escribir_una_vez()
    print("sha256:", hash_archivo())
