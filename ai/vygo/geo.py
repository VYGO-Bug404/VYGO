"""Rejilla L0/L1: NxN celdas, distancia Manhattan, tiempo de viaje con multiplicador de
zona/hora/clima. NumPy puro; la parte cara (distancia entre las N*N celdas) se precalcula
una sola vez al construir el objeto — `travel()` es un lookup en esa matriz más un
multiplicador barato.

Nota de diseño (FIFO): el multiplicador por hora se interpola linealmente entre anclas
horarias en vez de usar un escalón discreto por franja. Un escalón discreto puede violar
FIFO: si el multiplicador cae de una franja a la siguiente, salir un instante después del
corte puede llegar antes que saliendo un instante antes, sin importar qué tan pequeño sea
el salto de tiempo (ver la prueba en tests/test_invariants.py). La interpolación lineal
mantiene la derivada del multiplicador acotada, lo que sí garantiza FIFO para cualquier
viaje de esta rejilla (demostración en el docstring de `travel`).
"""

from __future__ import annotations

import numpy as np

from vygo.schema import Clima, Vehiculo, VEHICULOS

SEGUNDOS_DIA = 86400.0

# Multiplicador de clima (γ_w) -- constante en el tiempo, escala directa del tiempo de viaje.
# Valores en línea con docs/modelo-matematico.md §5.3, extendidos a los 5 climas simulables
# de vygo.schema.CLIMA_SIMULABLE.
CLIMA_MULT: dict[Clima, float] = {
    Clima.DESPEJADO: 1.00,
    Clima.NUBLADO: 1.05,
    Clima.LLUVIA: 1.15,
    Clima.LLUVIA_FUERTE: 1.30,
    Clima.TORMENTA: 1.50,
}


def _perfil_hora_default(n_franjas: int) -> np.ndarray:
    """Curva suave de congestión por hora del día: dos picos anchos (mañana/tarde) sobre una
    base de 1.0. La amplitud y el ancho están elegidos para que ninguna ancla cambie más
    rápido que el límite que exige FIFO en esta rejilla (ver GridWorld.travel)."""
    horas = np.arange(n_franjas, dtype=np.float64) * (24.0 / n_franjas)
    pico_manana = np.exp(-0.5 * ((horas - 8.5) / 2.0) ** 2)
    pico_tarde = np.exp(-0.5 * ((horas - 18.5) / 2.0) ** 2)
    return 1.0 + 0.20 * pico_manana + 0.25 * pico_tarde


class GridWorld:
    """Rejilla NxN de celdas cuadradas de `cell_size_m` metros (default 20x20 @ 500 m).
    Distancia y tiempo Manhattan. La matriz de distancias y de tiempo-base (a velocidad de
    referencia, sin multiplicadores) entre las N*N celdas se precalcula una sola vez al
    construir el objeto.
    """

    def __init__(
        self,
        n: int = 20,
        cell_size_m: float = 500.0,
        vehiculo: Vehiculo = Vehiculo.MOTO,
        n_franjas_hora: int = 24,
        perfil_hora: np.ndarray | None = None,
        seed: int = 0,
    ) -> None:
        self.n = n
        self.cell_size_m = float(cell_size_m)
        self.vehiculo = vehiculo
        self.n_franjas_hora = n_franjas_hora

        perfil_vehiculo = VEHICULOS[vehiculo]
        self.velocidad_base_ms = perfil_vehiculo.velocidad_base_kmh * 1000.0 / 3600.0

        n_celdas = n * n
        filas, cols = np.divmod(np.arange(n_celdas), n)
        dfila = np.abs(filas[:, None] - filas[None, :])
        dcol = np.abs(cols[:, None] - cols[None, :])
        # Matrices completas (n_celdas x n_celdas): O(1) por consulta desde aquí en adelante.
        self.dist_m = (dfila + dcol).astype(np.float64) * self.cell_size_m
        self.tiempo_base_s = self.dist_m / self.velocidad_base_ms

        if perfil_hora is None:
            perfil_hora = _perfil_hora_default(n_franjas_hora)
        if perfil_hora.shape != (n_franjas_hora,):
            raise ValueError("perfil_hora debe tener shape (n_franjas_hora,)")
        self.mult_hora = perfil_hora.astype(np.float64)

        rng = np.random.default_rng(seed)
        self.densidad = rng.gamma(shape=2.0, scale=0.3, size=(n, n)).clip(0.0, 3.0)
        # Congestión por zona: proporcional a la densidad local, 1.0x a 1.4x.
        self.mult_zona = 1.0 + 0.4 * (self.densidad / self.densidad.max())

    def _indice(self, celda: tuple[int, int]) -> int:
        fila, col = celda
        return fila * self.n + col

    def _mult_hora_en(self, t: float) -> float:
        segundos_del_dia = t % SEGUNDOS_DIA
        ancho_franja = SEGUNDOS_DIA / self.n_franjas_hora
        pos = segundos_del_dia / ancho_franja
        i0 = int(pos) % self.n_franjas_hora
        i1 = (i0 + 1) % self.n_franjas_hora
        frac = pos - int(pos)
        return float(self.mult_hora[i0] * (1.0 - frac) + self.mult_hora[i1] * frac)

    def travel(
        self, origen: tuple[int, int], destino: tuple[int, int], t: float, clima: Clima,
    ) -> tuple[float, float]:
        """(segundos, metros) para ir de `origen` a `destino` saliendo en el instante `t`.

        FIFO: t + travel(t)[0] es no decreciente en t. Se cumple porque el multiplicador
        total mult(t) = mult_zona * mult_hora(t) * mult_clima es Lipschitz en t (mult_zona y
        mult_clima son constantes en t; mult_hora es lineal a trozos entre anclas horarias),
        con pendiente acotada por 2*max(amplitud)/ancho_franja. Mientras esa pendiente sea
        menor que 1/(tiempo_base_maximo*mult_zona_max*mult_clima_max), ningún adelanto de
        salida puede "adelantar" la llegada. El perfil default deja margen amplio (~3x) para
        esta rejilla; un `perfil_hora` custom con picos más agresivos podría romperlo.
        """
        i, j = self._indice(origen), self._indice(destino)
        distancia_m = float(self.dist_m[i, j])
        mult_zona = 0.5 * (float(self.mult_zona.flat[i]) + float(self.mult_zona.flat[j]))
        mult = mult_zona * self._mult_hora_en(t) * CLIMA_MULT[clima]
        tiempo_s = float(self.tiempo_base_s[i, j]) * mult
        return tiempo_s, distancia_m

    def densidad_local(self, celda: tuple[int, int]) -> float:
        fila, col = celda
        return float(self.densidad[fila, col])
