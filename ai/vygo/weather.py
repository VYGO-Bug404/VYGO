"""Cadena de Markov de clima: 5 estados (vygo.schema.CLIMA_SIMULABLE), paso de 15 min.
Matriz de transición y multiplicadores en config/clima.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from vygo.schema import CLIMA_SIMULABLE, Clima

_CONFIG_DEFAULT = Path(__file__).resolve().parent.parent / "config" / "clima.yaml"

# Índice fijo 0..4 = CLIMA_SIMULABLE, en ese orden. Todo lo que sigue está indexado así.
_INDICE_DE_CLIMA = {c: i for i, c in enumerate(CLIMA_SIMULABLE)}


def _cargar_config(ruta: Path = _CONFIG_DEFAULT) -> dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class ParametrosClima:
    """Matriz de transición (5x5) y multiplicadores (5,) cargados de config/clima.yaml."""

    transicion: np.ndarray
    mult_tiempo_viaje: np.ndarray
    mult_demanda: np.ndarray
    mult_tarifa: np.ndarray
    paso_segundos: float

    @classmethod
    def desde_yaml(cls, ruta: Path = _CONFIG_DEFAULT) -> "ParametrosClima":
        cfg = _cargar_config(ruta)
        orden = list(CLIMA_SIMULABLE)
        filas = cfg["transicion"]
        transicion = np.array([filas[c.value] for c in orden], dtype=np.float64)
        if not np.allclose(transicion.sum(axis=1), 1.0, atol=1e-6):
            raise ValueError("cada fila de la matriz de transición de clima debe sumar 1.0")
        mult = cfg["multiplicadores"]
        return cls(
            transicion=transicion,
            mult_tiempo_viaje=np.array(mult["tiempo_viaje"], dtype=np.float64),
            mult_demanda=np.array(mult["demanda"], dtype=np.float64),
            mult_tarifa=np.array(mult["tarifa"], dtype=np.float64),
            paso_segundos=float(cfg.get("paso_segundos", 900)),
        )


@dataclass
class CadenaClima:
    """Estado de clima simulado. `avanzar(t)` hace tantos pasos de Markov como franjas de
    `paso_segundos` hayan transcurrido desde la última llamada."""

    parametros: ParametrosClima
    estado: Clima = Clima.DESPEJADO
    rng: np.random.Generator = field(default_factory=np.random.default_rng)
    _t_ultimo_paso: float = 0.0

    @classmethod
    def crear(
        cls, seed: int = 0, estado_inicial: Clima = Clima.DESPEJADO, ruta_config: Path = _CONFIG_DEFAULT,
    ) -> "CadenaClima":
        return cls(
            parametros=ParametrosClima.desde_yaml(ruta_config),
            estado=estado_inicial,
            rng=np.random.default_rng(seed),
        )

    def avanzar(self, t: float) -> Clima:
        """Avanza la cadena hasta el instante `t` (segundos desde el inicio del episodio),
        dando un paso de Markov por cada `paso_segundos` transcurridos. Devuelve el estado
        vigente en `t` (puede ser el mismo si no se cruzó ninguna franja)."""

        pasos = int(t // self.parametros.paso_segundos) - int(self._t_ultimo_paso // self.parametros.paso_segundos)
        idx = _INDICE_DE_CLIMA[self.estado]
        for _ in range(max(0, pasos)):
            idx = int(self.rng.choice(len(CLIMA_SIMULABLE), p=self.parametros.transicion[idx]))
        self.estado = CLIMA_SIMULABLE[idx]
        self._t_ultimo_paso = t
        return self.estado

    def mult_tiempo_viaje(self, clima: Clima | None = None) -> float:
        return float(self.parametros.mult_tiempo_viaje[_INDICE_DE_CLIMA[clima or self.estado]])

    def mult_demanda(self, clima: Clima | None = None) -> float:
        return float(self.parametros.mult_demanda[_INDICE_DE_CLIMA[clima or self.estado]])

    def mult_tarifa(self, clima: Clima | None = None) -> float:
        return float(self.parametros.mult_tarifa[_INDICE_DE_CLIMA[clima or self.estado]])
