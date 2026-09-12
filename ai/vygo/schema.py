"""Dataclasses y enums espejo del esquema real de VYGO (Supabase/PostgreSQL 17 + PostGIS).

Los nombres de campo coinciden exactamente con las columnas de la base de datos
(ver docs/vygo-ai-training.pdf, Parte I — Base de Datos VYGO). No renombrar ni cambiar
tipos sin actualizar ese documento y ai/CLAUDE.md §3/§5 primero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Optional

# geography(Point,4326) en la BD -> tupla (lat, lon) en el simulador.
Coordenada = tuple[float, float]


class App(IntEnum):
    """Espejo de la tabla `apps` (catálogo de plataformas conectadas)."""

    UBER = 1
    DIDI = 2
    RAPPI = 3


class EstadoPedido(str, Enum):
    """Espejo de `pedidos.estado`."""

    CREADO = "creado"
    BUSCANDO = "buscando"
    ASIGNADO = "asignado"
    EN_CAMINO = "en_camino"
    ENTREGADO = "entregado"
    CANCELADO = "cancelado"


class EstadoOferta(str, Enum):
    """Espejo de `ofertas_pedido.estado`."""

    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    EXPIRADA = "expirada"
    PERDIDA = "perdida"
    CANCELADA = "cancelada"


class ResultadoDifusion(str, Enum):
    """Espejo de `difusiones_pedido.resultado`."""

    ACEPTADA = "aceptada"
    SIN_RESPUESTA = "sin_respuesta"
    CANCELADA = "cancelada"


class Clima(str, Enum):
    """Espejo de `pedidos.clima` / `ofertas_pedido.clima` / `difusiones_pedido.clima`."""

    DESPEJADO = "despejado"
    NUBLADO = "nublado"
    LLUVIA = "lluvia"
    LLUVIA_FUERTE = "lluvia_fuerte"
    TORMENTA = "tormenta"
    OTRO = "otro"


# vygo/weather.py simula una cadena de Markov de 5 estados (ai/CLAUDE.md §4). OTRO existe
# en el CHECK de la BD como categoría residual, pero el generador nunca lo produce.
CLIMA_SIMULABLE: tuple[Clima, ...] = (
    Clima.DESPEJADO,
    Clima.NUBLADO,
    Clima.LLUVIA,
    Clima.LLUVIA_FUERTE,
    Clima.TORMENTA,
)


class Vehiculo(str, Enum):
    """Espejo de `repartidores.vehiculo`."""

    MOTO = "moto"
    AUTO = "auto"
    BICI = "bici"


@dataclass(slots=True, frozen=True)
class PerfilVehiculo:
    """Parámetros físicos de un tipo de vehículo (no está en la BD; es config del simulador)."""

    capacidad: int  # Q: pedidos simultáneos a bordo
    velocidad_base_kmh: float
    rendimiento_max_kml: Optional[float]  # None = sin combustible (bici)
    velocidad_max_rendimiento_kmh: Optional[float]


VEHICULOS: dict[Vehiculo, PerfilVehiculo] = {
    Vehiculo.MOTO: PerfilVehiculo(
        capacidad=2,
        velocidad_base_kmh=32.0,
        rendimiento_max_kml=45.0,
        velocidad_max_rendimiento_kmh=45.0,
    ),
    Vehiculo.AUTO: PerfilVehiculo(
        capacidad=6,
        velocidad_base_kmh=28.0,
        rendimiento_max_kml=14.0,
        velocidad_max_rendimiento_kmh=50.0,
    ),
    Vehiculo.BICI: PerfilVehiculo(
        capacidad=1,
        velocidad_base_kmh=14.0,
        rendimiento_max_kml=None,
        velocidad_max_rendimiento_kmh=None,
    ),
}


@dataclass(slots=True)
class Pedido:
    """Espejo de la tabla `pedidos`."""

    id: str
    app_id: App
    origen: Coordenada
    destino: Coordenada
    estado: EstadoPedido
    clima: Clima
    creado_en: datetime
    id_externo: Optional[str] = None
    cliente_id: Optional[str] = None
    origen_direccion: Optional[str] = None
    destino_direccion: Optional[str] = None
    contexto: dict = field(default_factory=dict)
    precio: Optional[float] = None
    moneda: str = "MXN"
    aceptado_en: Optional[datetime] = None
    entregado_en: Optional[datetime] = None


@dataclass(slots=True)
class Oferta:
    """Espejo de la tabla `ofertas_pedido`."""

    id: str
    pedido_id: str
    repartidor_id: str
    radio_metros: float
    estado: EstadoOferta
    clima: Clima
    ofrecida_en: datetime
    viaje_id: Optional[str] = None
    ronda: int = 1
    desvio_estimado_metros: Optional[float] = None
    respondida_en: Optional[datetime] = None
    expira_en: Optional[datetime] = None


@dataclass(slots=True)
class Difusion:
    """Espejo de la tabla `difusiones_pedido` (una ronda de búsqueda de repartidor)."""

    id: str
    pedido_id: str
    ronda: int
    radio_metros: float
    total_ofertas: int
    clima: Clima
    iniciada_en: datetime
    cerrada_en: Optional[datetime] = None
    resultado: Optional[ResultadoDifusion] = None


@dataclass(slots=True)
class ViajePedido:
    """Espejo de la tabla pivote `viaje_pedidos` (pedido <-> viaje, con orden de visita)."""

    id: str
    viaje_id: str
    pedido_id: str
    agregado_en: datetime
    orden: int = 1


@dataclass(slots=True)
class Repartidor:
    """Espejo de la tabla `repartidores`."""

    id: str
    usuario_id: str
    creado_en: datetime
    app_id: Optional[App] = None
    vehiculo: Optional[Vehiculo] = None
    rating: float = 5.00
    disponible: bool = True


@dataclass(slots=True)
class Configuracion:
    """Espejo de la tabla clave-valor `configuracion`."""

    clave: str
    valor: str
    actualizado_en: datetime
    descripcion: Optional[str] = None
