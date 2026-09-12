"""Llegada de pedidos (Poisson no homogéneo) y difusión por rondas con anillos de
prioridad (ai/CLAUDE.md §3). El generador no crea datos nuevos del mundo real: simula el
mecanismo ya descrito para que el agente entrene contra algo con la misma estructura.

Mecanismo de difusión (clave del problema, ai/CLAUDE.md §3): la notificación de un pedido
se envía a TODOS los repartidores disponibles (aquí: el agente + N competidores sintéticos).
Los radios 1500/3000/5000 m son anillos de prioridad por distancia vectorial al origen, no
un radio de búsqueda expandido. Al cerrar la ronda (45 s) gana el del anillo más interno;
dentro del mismo anillo, el más cercano; empate, quien respondió antes. Los demás que
aceptaron -> 'perdida'. Sin aceptaciones -> 'sin_respuesta' y ronda siguiente (radio no
cambia de significado, pero la ronda avanza). Tras la ronda 3, 'cancelado'.

Ganchos para el evento de media jornada (NO implementado todavía, sólo el punto de
extensión): `modificador(t, zona) -> (mult_tarifa, mult_demanda)`, aplicado multiplicando
sobre la tarifa/demanda ya calculadas. `zona` es la celda (fila, col) del comercio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from vygo.geo import GridWorld
from vygo.schema import App, Clima
from vygo.weather import CadenaClima

RADIOS_ANILLO_M: tuple[float, ...] = (1500.0, 3000.0, 5000.0)
DURACION_RONDA_S = 45.0
MAX_RONDAS = 3
EXPIRA_OFERTA_S = 30.0

_TARIFA_BASE_MXN = (28.0, 38.0)
# Bajado de (7,11) a (6,8) MXN/km (tarea "economia corregida"): revisada la contabilidad
# completa (ingreso, costo por km, conversión de horas) y no hay bug de conversión --
# rho_hat salía en 227-275 MXN/h porque la tarifa por km era generosa, no por un factor de
# unidades mal aplicado. Ver ai/reports/HANDOFF.md para el desglose antes/después.
_TARIFA_BETA_KM_MXN = (6.0, 8.0)
# Subido el techo de 25 a 35 min (mismo motivo que la intensidad, ver más abajo): más
# tiempo de preparación es más holgura natural (sigma_i) para que aceptar un segundo
# pedido cercano "quepa gratis" en la espera del primero -- eso es lo que hace rentable
# agrupar en el modelo (docs/modelo-matematico.md §1.3).
_PREP_MEDIA_MIN = (6.0, 35.0)
N_COMPETIDORES_BASE = 25

# Geografía por clústeres (tarea "diagnostico de agrupamiento y clusters de comercios"):
# reemplaza el muestreo por densidad de fondo sobre TODA la rejilla -- ese esquema dispersa
# los comercios uniformemente aunque unas celdas pesen más, así que dos comercios rara vez
# caen a <1km uno del otro. Replica plazas comerciales / corredores gastronómicos reales:
# N_ZONAS_DENSAS focos, N_COMERCIOS_POR_ZONA comercios cada uno dentro de un disco de radio
# RADIO_ZONA_M, más N_COMERCIOS_DISPERSOS de relleno sobre el resto de la rejilla.
N_ZONAS_DENSAS = 4
N_COMERCIOS_POR_ZONA = 15
N_COMERCIOS_DISPERSOS = 20
RADIO_ZONA_M = 1500.0
# Destinos: dentro de este radio del comercio de ORIGEN, no un kernel sobre toda la rejilla
# (docs/modelo-matematico.md §1.3: la entrega de comida queda cerca de donde se cocinó).
RADIO_DESTINO_M = 2500.0

ModificadorFn = Callable[[float, tuple[int, int]], tuple[float, float]]


@dataclass(slots=True, frozen=True)
class Comercio:
    id: str
    pos: tuple[int, int]
    prep_media_s: float
    intensidad: float  # peso relativo (>0) en la tasa de llegada; refleja la densidad local


@dataclass(slots=True)
class PedidoGenerado:
    """Lo que el generador produce; env.py lo traduce a `schema.Pedido` para exportar."""

    id: str
    app: App
    comercio_id: str
    origen: tuple[int, int]
    destino: tuple[int, int]
    precio: float
    creado_en: float
    tiempo_listo_en: float
    fecha_limite: float
    theta_frescura: float
    clima: Clima


@dataclass(slots=True)
class Difusion:
    pedido_id: str
    ronda: int
    radio_metros: float
    iniciada_en: float
    cierra_en: float


def _perfil_llegada_hora(t: float) -> float:
    """Multiplicador de demanda por hora del día: picos 13:00-15:00 y 19:00-21:30 sobre
    una base de 1.0 (mismo espíritu que geo._perfil_hora_default, pero de demanda)."""
    hora = (t % 86400.0) / 3600.0
    pico_comida = math.exp(-0.5 * ((hora - 14.0) / 1.2) ** 2)
    pico_cena = math.exp(-0.5 * ((hora - 20.25) / 1.5) ** 2)
    return 1.0 + 1.8 * pico_comida + 1.4 * pico_cena


def _centros_zonas(grid: GridWorld, n_zonas: int) -> list[tuple[float, float]]:
    """Centros repartidos en cuadrícula (sqrt(n_zonas) x sqrt(n_zonas) si es cuadrado
    perfecto, si no en una franja) sobre el interior de la rejilla -- con margen suficiente
    para que un disco de radio `RADIO_ZONA_M` quepa sin salirse. Con n_zonas=4 da los 4
    cuadrantes clásicos: (n/4, n/4), (n/4, 3n/4), (3n/4, n/4), (3n/4, 3n/4)."""

    lado = math.isqrt(n_zonas)
    if lado * lado != n_zonas:
        # Fallback genérico (no es el caso por defecto n_zonas=4): franja 1 x n_zonas.
        paso = grid.n / (n_zonas + 1)
        return [(grid.n / 2.0, paso * (i + 1)) for i in range(n_zonas)]
    paso = grid.n / (lado + 1)
    return [(paso * (fi + 1), paso * (ci + 1)) for fi in range(lado) for ci in range(lado)]


def _muestrear_en_disco(
    centro: tuple[float, float], radio_celdas: float, grid: GridWorld, rng: np.random.Generator,
) -> tuple[int, int]:
    """Punto uniforme en área dentro del disco (r = radio*sqrt(u), no r = radio*u, para no
    sobre-concentrar en el centro), recortado a los bordes de la rejilla."""

    r = radio_celdas * math.sqrt(float(rng.uniform(0.0, 1.0)))
    angulo = float(rng.uniform(0.0, 2 * math.pi))
    fila = int(round(centro[0] + r * math.sin(angulo)))
    col = int(round(centro[1] + r * math.cos(angulo)))
    fila = min(max(fila, 0), grid.n - 1)
    col = min(max(col, 0), grid.n - 1)
    return fila, col


def muestrear_comercios(grid: GridWorld, m: int, rng: np.random.Generator) -> list[Comercio]:
    """CLÚSTERES explícitos, no densidad de fondo: `N_ZONAS_DENSAS` focos de alta
    concentración (comercios dentro de un disco de radio `RADIO_ZONA_M` cada uno) más una
    fracción dispersa de relleno sobre el resto de la rejilla, en la misma proporción que
    `N_COMERCIOS_POR_ZONA`*`N_ZONAS_DENSAS` : `N_COMERCIOS_DISPERSOS` (60:20 con `m`=80, los
    valores de la tarea). Con `m` distinto de 80 se escala la misma proporción. Esto es lo
    que permite que dos recolecciones estén a <1km -- el muestreo por densidad de fondo
    anterior las dispersaba sobre TODA la rejilla aunque unas celdas pesaran más."""

    fraccion_dispersos = N_COMERCIOS_DISPERSOS / (N_ZONAS_DENSAS * N_COMERCIOS_POR_ZONA + N_COMERCIOS_DISPERSOS)
    n_dispersos = max(0, round(m * fraccion_dispersos))
    n_agrupados = m - n_dispersos
    radio_zona_celdas = RADIO_ZONA_M / grid.cell_size_m
    centros = _centros_zonas(grid, N_ZONAS_DENSAS)

    comercios: list[Comercio] = []
    for z, centro in enumerate(centros):
        n_zona = n_agrupados // len(centros) + (1 if z < n_agrupados % len(centros) else 0)
        for _ in range(n_zona):
            fila, col = _muestrear_en_disco(centro, radio_zona_celdas, grid, rng)
            media_min = rng.uniform(*_PREP_MEDIA_MIN)
            comercios.append(Comercio(
                id=f"c{len(comercios)}", pos=(fila, col), prep_media_s=media_min * 60.0,
                intensidad=float(grid.densidad[fila, col]),
            ))

    for _ in range(n_dispersos):
        fila = int(rng.integers(0, grid.n))
        col = int(rng.integers(0, grid.n))
        media_min = rng.uniform(*_PREP_MEDIA_MIN)
        comercios.append(Comercio(
            id=f"c{len(comercios)}", pos=(fila, col), prep_media_s=media_min * 60.0,
            intensidad=float(grid.densidad[fila, col]),
        ))

    return comercios


@dataclass
class GeneradorPedidos:
    grid: GridWorld
    comercios: list[Comercio]
    clima: CadenaClima
    rng: np.random.Generator
    n_pedidos_creados: int = 0
    n_competidores_base: int = N_COMPETIDORES_BASE
    modificador: Optional[ModificadorFn] = None
    clima_variable: bool = True  # False en L0: clima fijo (DESPEJADO), sin cadena de Markov
    prep_variable: bool = True  # False en L0: preparación fija (media del comercio), sin LogNormal

    @classmethod
    def crear(
        cls, grid: GridWorld, m_comercios: int = 200, seed: int = 0,
        clima: Optional[CadenaClima] = None, nivel: str = "L1",
    ) -> "GeneradorPedidos":
        rng = np.random.default_rng(seed)
        comercios = muestrear_comercios(grid, m_comercios, rng)
        es_l0 = nivel == "L0"
        return cls(
            grid=grid, comercios=comercios, clima=clima or CadenaClima.crear(seed=seed), rng=rng,
            n_competidores_base=0 if es_l0 else N_COMPETIDORES_BASE,
            clima_variable=not es_l0, prep_variable=not es_l0,
        )

    def _clima_actual(self, t: float) -> Clima:
        return self.clima.avanzar(t) if self.clima_variable else self.clima.estado

    def _modificador_en(self, t: float, zona: tuple[int, int]) -> tuple[float, float]:
        if self.modificador is None:
            return 1.0, 1.0
        return self.modificador(t, zona)

    def _intensidad_efectiva(self, t: float, comercio: Comercio) -> float:
        """Intensidad base del comercio, escalada por el multiplicador de DEMANDA del
        modificador de evento activo en su zona (§ SURGE, eventos.py) -- antes de la tarea
        "evento de media jornada" este multiplicador se calculaba pero nunca se aplicaba
        aquí (bug real: sólo se usaba mult_tarifa en `_tarifa`, mult_demanda quedaba
        calculado y descartado). Usado tanto para la tasa total (`_lambda_total`) como para
        el peso de selección de comercio (`_crear_pedido`) -- deben ser la MISMA intensidad
        efectiva o un surge subiría la tasa global sin concentrar los pedidos en su zona."""
        _mult_tarifa, mult_demanda = self._modificador_en(t, comercio.pos)
        return comercio.intensidad * mult_demanda

    def _lambda_total(self, t: float) -> float:
        clima_actual = self._clima_actual(t)
        mult_clima = self.clima.mult_demanda(clima_actual)
        mult_hora = _perfil_llegada_hora(t)
        intensidad_total = sum(self._intensidad_efectiva(t, c) for c in self.comercios)
        # Subido de 1/90s a 1/30s (3x): con 1/90s la prueba de sanidad (ver
        # reports/HANDOFF.md) daba bundling~0.97 y B2 apenas +9.3% sobre B1 -- muy poca
        # concurrencia de pedidos visibles a la vez como para que agrupar valga la pena.
        lambda_base_por_unidad_intensidad = 1.0 / 30.0  # ~1 pedido/30s en el comercio promedio
        lam = intensidad_total * lambda_base_por_unidad_intensidad * mult_hora * mult_clima
        return lam

    def siguiente_pedido(self, t: float) -> tuple[float, PedidoGenerado]:
        """Poisson no homogéneo por adelgazamiento (thinning): (instante, pedido) del
        siguiente pedido a partir de `t`. Lambda(t, zona, clima): la zona entra vía la
        intensidad de cada comercio (§ muestrear_comercios) y el modificador de evento."""

        lambda_max = self._lambda_max_cota(t)
        t_actual = t
        while True:
            t_actual += float(self.rng.exponential(1.0 / lambda_max))
            if self.rng.uniform() <= self._lambda_total(t_actual) / lambda_max:
                return t_actual, self._crear_pedido(t_actual)

    def _lambda_max_cota(self, t: float, ventana_s: float = 3 * 3600.0) -> float:
        muestras = [self._lambda_total(t + dt) for dt in np.linspace(0.0, ventana_s, 6)]
        return max(muestras) * 1.5 + 1e-6

    def _crear_pedido(self, t: float) -> PedidoGenerado:
        pesos = np.array([self._intensidad_efectiva(t, c) for c in self.comercios])
        comercio = self.comercios[int(self.rng.choice(len(self.comercios), p=pesos / pesos.sum()))]
        destino = self._muestrear_destino(comercio.pos)
        clima_actual = self._clima_actual(t)
        distancia_km = (
            (abs(destino[0] - comercio.pos[0]) + abs(destino[1] - comercio.pos[1]))
            * self.grid.cell_size_m / 1000.0
        )
        app = list(App)[int(self.rng.integers(0, len(App)))]
        precio = self._tarifa(distancia_km, clima_actual, comercio.pos, t)
        if self.prep_variable:
            prep_s = float(self.rng.lognormal(mean=math.log(comercio.prep_media_s), sigma=0.4))
        else:
            prep_s = comercio.prep_media_s
        tiempo_listo_en = t + prep_s

        # Fecha límite: ANCLADA a creado_en (t), no a tiempo_listo_en (tarea "aprieta las
        # fechas límite") -- antes el margen de preparación (6-35 min) se sumaba GRATIS
        # encima del límite, así que éste nunca ataba de verdad (puntualidad=1.00 exacta en
        # las tres políticas: la tensión central del problema no existía). Ahora el tiempo
        # de preparación CUENTA contra el límite, igual que en la vida real -- un pedido no
        # deja de tener prisa sólo porque la cocina tarda.
        dt_directo, _dm = self.grid.travel(comercio.pos, destino, tiempo_listo_en, clima_actual)
        fecha_limite = t + dt_directo * 1.6 + 20 * 60.0
        theta_frescura = float(self.rng.uniform(900.0, 2400.0))

        self.n_pedidos_creados += 1
        return PedidoGenerado(
            id=f"p{self.n_pedidos_creados}", app=app, comercio_id=comercio.id,
            origen=comercio.pos, destino=destino, precio=precio, creado_en=t,
            tiempo_listo_en=tiempo_listo_en, fecha_limite=fecha_limite,
            theta_frescura=theta_frescura, clima=clima_actual,
        )

    def _muestrear_destino(self, origen: tuple[int, int]) -> tuple[int, int]:
        """Dentro de `RADIO_DESTINO_M` del comercio de ORIGEN (no un kernel sobre toda la
        rejilla): las entregas quedan cerca de donde se cocinó, lo que además hace que dos
        pedidos del mismo corredor gastronómico compartan zona de entrega."""
        radio_celdas = RADIO_DESTINO_M / self.grid.cell_size_m
        return _muestrear_en_disco(origen, radio_celdas, self.grid, self.rng)

    def _tarifa(self, distancia_km: float, clima: Clima, zona: tuple[int, int], t: float) -> float:
        base = float(self.rng.uniform(*_TARIFA_BASE_MXN))
        beta = float(self.rng.uniform(*_TARIFA_BETA_KM_MXN))
        ruido = float(self.rng.lognormal(mean=0.0, sigma=0.15))
        mult_clima = self.clima.mult_tarifa(clima)
        mult_tarifa_evento, _mult_demanda_evento = self._modificador_en(t, zona)
        return (base + beta * distancia_km) * ruido * mult_clima * mult_tarifa_evento

    # ---- difusión por rondas (anillos de prioridad) ------------------------------

    def iniciar_difusion(self, pedido: PedidoGenerado, ronda: int, t: float) -> Difusion:
        radio = RADIOS_ANILLO_M[min(ronda, len(RADIOS_ANILLO_M)) - 1]
        return Difusion(pedido_id=pedido.id, ronda=ronda, radio_metros=radio, iniciada_en=t, cierra_en=t + DURACION_RONDA_S)

    def anillo_de(self, distancia_m: float) -> int:
        """1/2/3 = anillo; 4 = fuera de todos los anillos (no elegible)."""
        for i, radio in enumerate(RADIOS_ANILLO_M, start=1):
            if distancia_m <= radio:
                return i
        return 4

    def n_competidores_efectivos(self, pos_origen: tuple[int, int], clima: Clima) -> int:
        densidad_local = self.grid.densidad_local(pos_origen) / max(self.grid.densidad.mean(), 1e-9)
        mult_clima = 1.0 + 0.3 * (self.clima.mult_demanda(clima) - 1.0)
        return max(0, int(round(self.n_competidores_base * densidad_local * mult_clima)))

    def p_gana_estimada(self, distancia_m: float, n_competidores_efectivos: int) -> float:
        """P(nadie está más cerca que el repartidor), asumiendo competidores uniformes en
        el área del anillo 3 (adelgazamiento de Poisson). Feature precalculado (§6) y
        estimador rápido para baselines; `resolver_ronda` simula competidores concretos
        para la resolución REAL."""

        radio_max = RADIOS_ANILLO_M[-1]
        area_propia = math.pi * min(distancia_m, radio_max) ** 2
        area_total = math.pi * radio_max ** 2
        lam = n_competidores_efectivos * (area_propia / area_total)
        return math.exp(-lam)

    def resolver_ronda(
        self,
        pedido: PedidoGenerado,
        difusion: Difusion,
        respuestas_reales: list[tuple[str, float, float]],
    ) -> tuple[Optional[str], list[str]]:
        """`respuestas_reales`: (repartidor_id, distancia_m, instante_respuesta) de quienes
        SÍ aceptaron esta ronda (normalmente 0 o 1: el propio agente). Corre N_comp
        competidores sintéticos (única función: que p_gana < 1) y devuelve
        (ganador_id o None, [perdedores_id])."""

        n_comp = self.n_competidores_efectivos(pedido.origen, pedido.clima)
        aceptaron: list[tuple[str, int, float, float]] = [
            (rid, self.anillo_de(dist), dist, t_resp) for rid, dist, t_resp in respuestas_reales
        ]

        prob_acepta_por_anillo = {1: 0.6, 2: 0.3, 3: 0.1}
        for c in range(n_comp):
            dist = float(self.rng.uniform(0.0, RADIOS_ANILLO_M[-1] * 1.2))
            anillo = self.anillo_de(dist)
            if anillo == 4:
                continue
            if self.rng.uniform() < prob_acepta_por_anillo[anillo]:
                t_resp = difusion.iniciada_en + float(self.rng.uniform(1.0, DURACION_RONDA_S))
                aceptaron.append((f"_comp{c}", anillo, dist, t_resp))

        if not aceptaron:
            return None, []

        aceptaron.sort(key=lambda x: (x[1], x[2], x[3]))
        ganador = aceptaron[0][0]
        perdedores = [rid for rid, *_ in aceptaron[1:] if not rid.startswith("_comp")]
        return ganador, perdedores
