"""Verifica que la reacción a los eventos de media jornada (vygo/eventos.py) EMERGE de las
reglas existentes -- no se programa un caso especial en ningún lado:

- SURGE sube la tarifa de la oferta y `baselines.politica_umbral` la acepta sola porque la
  tasa marginal ya supera `rho_hat`, con la MISMA fórmula de siempre.
- CIERRE_VIAL cambia lo que `geo.GridWorld.travel` devuelve y `sequencer.held_karp`
  replanifica solo porque ve un `travel_fn` distinto -- no porque sepa que hay un evento.

Ver ai/reports/HANDOFF.md para el ejemplo narrado.
"""

from __future__ import annotations

from vygo.baselines import politica_umbral
from vygo.eventos import EventoCierreVial, EventoSurge, ProgramadorEventos
from vygo.feasibility import K_F
from vygo.geo import GridWorld
from vygo.insertion import EstadoRuta, OfertaCandidata
from vygo.schema import Clima
from vygo.sequencer import Restricciones, held_karp


def test_surge_emerge_como_aceptacion_via_umbral():
    grid = GridWorld(n=20, seed=0)
    pos_agente = (0, 0)
    pos_recogida = (0, 4)
    pos_entrega = (0, 10)
    t = 0.0

    dt_recogida, _dm = grid.travel(pos_agente, pos_recogida, t, Clima.DESPEJADO)
    dt_entrega, _dm2 = grid.travel(pos_recogida, pos_entrega, t, Clima.DESPEJADO)
    dt_total = dt_recogida + dt_entrega

    # Precio elegido para que la tasa marginal SIN evento caiga debajo de rho_hat, y CON el
    # surge (x1.4) quede por encima -- ni la máscara ni la política se tocan, sólo el precio
    # que ve la oferta cambia (exactamente lo que hace generator._tarifa cuando el
    # modificador de zona está activo).
    rho_hat = 150.0
    precio_base = rho_hat * (dt_total / 3600.0) * 0.9

    restricciones = Restricciones(capacidad=10, r={}, l={}, theta={}, carga={})

    def _oferta(precio: float) -> OfertaCandidata:
        return OfertaCandidata(
            id="p0", pos_recogida=pos_recogida, pos_entrega=pos_entrega,
            r=0.0, l=None, theta=None, carga=1, expira_en=None,
            precio=precio, anillo=1, p_gana_estimada=1.0,
        )

    def _estado(oferta: OfertaCandidata) -> EstadoRuta:
        return EstadoRuta(
            t=t, pos=pos_agente, clima=Clima.DESPEJADO, plan=[], restricciones=restricciones,
            travel_fn=lambda a, b, tt: grid.travel(a, b, tt, Clima.DESPEJADO),
            ofertas=[oferta] + [None] * (K_F - 1),
        )

    accion_sin_evento = politica_umbral(_estado(_oferta(precio_base)), rho_hat)
    assert accion_sin_evento == K_F, "sin evento, la oferta no debe superar rho_hat (rechazar_todas)"

    surge = EventoSurge(
        inicia_min=0.0, duracion_min=45.0, zona=pos_recogida, radio_celdas=5.0,
        mult_tarifa=1.4, mult_intensidad=1.6,
    )
    mult_tarifa, mult_intensidad = ProgramadorEventos([surge]).modificador(t, pos_recogida)
    assert (mult_tarifa, mult_intensidad) == (1.4, 1.6)

    precio_con_surge = precio_base * mult_tarifa
    accion_con_evento = politica_umbral(_estado(_oferta(precio_con_surge)), rho_hat)
    assert accion_con_evento == 0, (
        "con SURGE activo, la MISMA oferta a 1.4x el precio debe superar rho_hat y "
        "aceptarse -- misma politica_umbral, mismo action_mask, nada especial para eventos"
    )


def test_cierre_vial_emerge_como_replanificacion_del_secuenciador():
    grid = GridWorld(n=20, seed=0)
    clima = Clima.DESPEJADO

    # Dos pedidos cuyas recogidas y entregas quedan a ambos lados de la columna 10 -- el
    # corredor que el evento va a cerrar.
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

    def _travel_sin_cierre(a, b, tt):
        return grid.travel(a, b, tt, clima)

    cierre = EventoCierreVial(inicia_min=0.0, duracion_min=40.0, eje="columna", indice=10, factor_detour=1.7)
    programador = ProgramadorEventos([cierre])

    def _travel_con_cierre(a, b, tt):
        return grid.travel(a, b, tt, clima, programador.corredores_cerrados(tt))

    _orden_sin, tiempo_sin, _dist_sin, _exacto_sin, _eval_sin = held_karp(
        stops, 0.0, (0, 0), _travel_sin_cierre, restricciones, k=20,
    )
    _orden_con, tiempo_con, _dist_con, _exacto_con, _eval_con = held_karp(
        stops, 0.0, (0, 0), _travel_con_cierre, restricciones, k=20,
    )

    assert tiempo_con > tiempo_sin, (
        "el mismo held_karp, con el MISMO travel_fn salvo por el corredor cerrado, debe "
        "encontrar un tiempo total mayor -- el secuenciador no sabe que hay un 'evento', "
        "sólo ve un travel_fn que ahora reporta viajes más caros al cruzar la columna 10"
    )

    # Y fuera de la ventana del evento (a los 41 min, ya cerró), el travel_fn vuelve a
    # coincidir con el caso sin cierre -- la reacción es transitoria, no permanente.
    t_despues = 41 * 60.0
    assert programador.corredores_cerrados(t_despues) == ()
    dt_normal = grid.travel((5, 5), (5, 15), t_despues, clima)
    dt_con_cierre_vencido = grid.travel((5, 5), (5, 15), t_despues, clima, programador.corredores_cerrados(t_despues))
    assert dt_normal == dt_con_cierre_vencido
