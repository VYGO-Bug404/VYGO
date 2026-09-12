"""Eventos guionados de media jornada (tarea "evento de media jornada, turnos congelados y
demo pareada"): SURGE (tarifa e intensidad de demanda suben en una zona, tiempo limitado) y
CIERRE_VIAL (un corredor del grid queda bloqueado, tiempo limitado). Se disparan a un minuto
fijo del turno, configurables en YAML (ver `cargar_eventos`).

LA REACCIÓN NO SE PROGRAMA. `ProgramadorEventos` sólo agrega los eventos activos en las DOS
interfaces que ya existían antes de esta tarea:

  - `generator.GeneradorPedidos.modificador(t, zona) -> (mult_tarifa, mult_demanda)`
  - `geo.GridWorld.travel(..., corredores_cerrados=...)`

Ni `baselines.politica_umbral` ni `sequencer.held_karp` saben que existe un "evento": sólo
ven una tarifa más alta o un tiempo de viaje más largo, y reaccionan con la MISMA regla de
siempre. Ver `tests/test_eventos.py` para la prueba de que la reacción emerge sola, con un
ejemplo concreto de cada tipo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import yaml

from vygo.geo import Corredor


@dataclass(frozen=True, slots=True)
class EventoSurge:
    inicia_min: float
    duracion_min: float
    zona: tuple[int, int]
    radio_celdas: float
    mult_tarifa: float
    mult_intensidad: float

    @property
    def fin_min(self) -> float:
        return self.inicia_min + self.duracion_min

    def activo_en(self, t: float) -> bool:
        minuto = t / 60.0
        return self.inicia_min <= minuto < self.fin_min

    def en_zona(self, celda: tuple[int, int]) -> bool:
        return math.hypot(celda[0] - self.zona[0], celda[1] - self.zona[1]) <= self.radio_celdas


@dataclass(frozen=True, slots=True)
class EventoCierreVial:
    inicia_min: float
    duracion_min: float
    eje: str  # "fila" | "columna"
    indice: int
    factor_detour: float = 1.7

    @property
    def fin_min(self) -> float:
        return self.inicia_min + self.duracion_min

    def activo_en(self, t: float) -> bool:
        minuto = t / 60.0
        return self.inicia_min <= minuto < self.fin_min

    def corredor(self) -> Corredor:
        return Corredor(eje=self.eje, indice=self.indice, factor_detour=self.factor_detour)


Evento = Union[EventoSurge, EventoCierreVial]


def cargar_eventos(ruta: str | Path) -> list[Evento]:
    """Formato YAML (lista bajo la clave `eventos`):

    eventos:
      - tipo: surge
        inicia_min: 60
        duracion_min: 45
        zona: [10, 10]
        radio_celdas: 4
        mult_tarifa: 1.4
        mult_intensidad: 1.6
      - tipo: cierre_vial
        inicia_min: 60
        duracion_min: 40
        eje: columna
        indice: 10
        factor_detour: 1.7
    """
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
    eventos: list[Evento] = []
    for e in datos.get("eventos", []):
        tipo = e["tipo"]
        if tipo == "surge":
            eventos.append(EventoSurge(
                inicia_min=float(e["inicia_min"]),
                duracion_min=float(e["duracion_min"]),
                zona=tuple(e["zona"]),
                radio_celdas=float(e["radio_celdas"]),
                mult_tarifa=float(e["mult_tarifa"]),
                mult_intensidad=float(e["mult_intensidad"]),
            ))
        elif tipo == "cierre_vial":
            eventos.append(EventoCierreVial(
                inicia_min=float(e["inicia_min"]),
                duracion_min=float(e["duracion_min"]),
                eje=e["eje"],
                indice=int(e["indice"]),
                factor_detour=float(e.get("factor_detour", 1.7)),
            ))
        else:
            raise ValueError(f"tipo de evento desconocido: {tipo!r}")
    return eventos


class ProgramadorEventos:
    """Agrega N eventos (list[Evento]) en las dos interfaces de enganche que
    generator.py/geo.py ya aceptaban antes de esta tarea, más un resumen de estado para
    instrumentar la observación (`estado_en`, ver env.py -- se coloca en un slot del bloque
    "plan activo" que ya está SIEMPRE en cero porque K_A_MAXIMO=4 < K_A=6, así que no hace
    falta tocar la dimensión de 186)."""

    def __init__(self, eventos: list[Evento]) -> None:
        self.eventos = eventos

    def modificador(self, t: float, zona: tuple[int, int]) -> tuple[float, float]:
        mult_tarifa, mult_intensidad = 1.0, 1.0
        for ev in self.eventos:
            if isinstance(ev, EventoSurge) and ev.activo_en(t) and ev.en_zona(zona):
                mult_tarifa *= ev.mult_tarifa
                mult_intensidad *= ev.mult_intensidad
        return mult_tarifa, mult_intensidad

    def corredores_cerrados(self, t: float) -> tuple[Corredor, ...]:
        return tuple(
            ev.corredor() for ev in self.eventos
            if isinstance(ev, EventoCierreVial) and ev.activo_en(t)
        )

    def estado_en(self, t: float) -> dict:
        surge_activo = 0.0
        cierre_activo = 0.0
        mult_tarifa_max = 1.0
        mult_intensidad_max = 1.0
        minutos_restantes = math.inf
        minuto = t / 60.0
        for ev in self.eventos:
            if not ev.activo_en(t):
                continue
            minutos_restantes = min(minutos_restantes, ev.fin_min - minuto)
            if isinstance(ev, EventoSurge):
                surge_activo = 1.0
                mult_tarifa_max = max(mult_tarifa_max, ev.mult_tarifa)
                mult_intensidad_max = max(mult_intensidad_max, ev.mult_intensidad)
            else:
                cierre_activo = 1.0
        if math.isinf(minutos_restantes):
            minutos_restantes = 0.0
        return {
            "surge_activo": surge_activo,
            "cierre_vial_activo": cierre_activo,
            "minutos_restantes_norm": min(minutos_restantes / 60.0, 1.0),
            "mult_tarifa_norm": mult_tarifa_max - 1.0,
            "mult_intensidad_norm": mult_intensidad_max - 1.0,
        }

    def evento_activo_tipo(self, t: float) -> str | None:
        """Para la demo/eval: nombre legible del evento activo en `t`, o None. Si hay más de
        uno activo (no ocurre en los escenarios de esta tarea, pero por si acaso) devuelve
        el primero que encuentre."""
        for ev in self.eventos:
            if ev.activo_en(t):
                return "surge" if isinstance(ev, EventoSurge) else "cierre_vial"
        return None
