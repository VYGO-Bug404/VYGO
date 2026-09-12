"""VygoEnv: entorno gymnasium L0/L1, dirigido por eventos (ai/CLAUDE.md §2, §6, §7).

La red sólo decide aceptar/rechazar/reposicionar; secuenciación (Held-Karp) y restricciones
duras (máscara de factibilidad) no se aprenden. `step()` avanza al SIGUIENTE evento
(llegada de oferta, cierre de ronda, expiración de oferta, llegada a un nodo del plan), no
a un tick fijo -- el reloj del episodio es el de los eventos, no el del wall-clock del step.

Épocas de evento:
  - "pedido": el generador produce un pedido nuevo; si hay slot libre (<K_F visibles) se
    muestra; si no, se encola.
  - "cierra_ronda": a los 45s de mostrarse una oferta, se resuelve contra competidores
    sintéticos (generator.resolver_ronda). Si el agente ganó, el pedido entra al plan.
  - "expira_oferta": a los 30s de mostrarse, si el agente no la aceptó, se retira del slot
    (no de la ronda: la ronda puede seguir resolviéndose con competidores).
  - "llega_nodo": el vehículo llega a la siguiente parada de su plan comprometido (recogida
    o entrega); genera el flujo de caja al entregar y libera capacidad.

Episodio = turno de 6 horas simuladas. `nivel` en {L0, L1}: L0 apaga clima variable,
competencia sintética y preparación variable (ver GeneradorPedidos.crear).
"""

from __future__ import annotations

import heapq
import math
from collections import deque
from typing import Any, Optional

import gymnasium
import numpy as np
from gymnasium import spaces

from vygo.feasibility import (
    HOLGURA_MINIMA_REPOSICIONAR_S,
    K_A_MAXIMO,
    K_F,
    action_mask,
    holguras_frescura_plan,
)
from vygo.features import K_A, ConstructorFeatures
from vygo.generator import DURACION_RONDA_S, EXPIRA_OFERTA_S, GeneradorPedidos, MAX_RONDAS, PedidoGenerado
from vygo.geo import GridWorld
from vygo.insertion import EstadoRuta, OfertaCandidata, eval_insertion
from vygo.schema import CLIMA_SIMULABLE, Vehiculo, VEHICULOS
from vygo.sequencer import Parada, Restricciones, held_karp, verificar_y_calendarizar
from vygo.weather import CadenaClima

DURACION_TURNO_S = 6 * 3600.0
# Tope de la cola de pedidos sin slot visible. K_F=8 slots x rondas de 45s ponen un techo
# duro de throughput (~8/45 pedidos/s); si la intensidad de llegada del generador lo supera
# (posible incluso en L0 con m_comercios chico), la cola crece sin límite y con ella el
# costo de mantenerla -- un pedido que ha esperado tanto sin ver un slot ya no es
# realista mantenerlo "vivo" indefinidamente, así que se cae (expira) al llegar al tope.
MAX_COLA_PENDIENTES = 40
COSTO_KM_MXN = 1.2  # c_kappa: combustible + mantenimiento, aproximado
PSI_RETRASO_MXN_MIN = 5.0  # penalización por minuto de retraso sobre la fecha límite
ALFA_RHO_HAT = 0.01
RHO_HAT_INICIAL = 100.0  # MXN/h


class VygoEnv(gymnasium.Env):
    """obs: Box(float32); action: Discrete(K_F + 2)
    K_F = 8 ofertas visibles; acción K_F = rechazar-todas; K_F+1 = reposicionarse."""

    metadata: dict[str, Any] = {"render_modes": []}

    def __init__(
        self, nivel: str = "L1", m_comercios: int = 200, vehiculo: Vehiculo = Vehiculo.MOTO,
        duracion_turno_s: float = DURACION_TURNO_S,
    ) -> None:
        if nivel not in ("L0", "L1"):
            raise ValueError("nivel debe ser 'L0' o 'L1'")
        self.nivel = nivel
        self.m_comercios = m_comercios
        self.vehiculo = vehiculo
        self.duracion_turno_s = duracion_turno_s
        self.action_space = spaces.Discrete(K_F + 2)
        dim = ConstructorFeatures().buffer.shape[0]
        self.observation_space = spaces.Box(low=-100.0, high=100.0, shape=(dim,), dtype=np.float32)
        self._constructor = ConstructorFeatures()

    # ------------------------------------------------------------------ reset ----

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        s = seed if seed is not None else 0
        self._rng = np.random.default_rng(s)

        self.grid = GridWorld(n=20, seed=s, vehiculo=self.vehiculo)
        clima = CadenaClima.crear(seed=s)
        self.generador = GeneradorPedidos.crear(self.grid, m_comercios=self.m_comercios, seed=s, clima=clima, nivel=self.nivel)

        self.t = 0.0
        self.pos = (self.grid.n // 2, self.grid.n // 2)
        self.capacidad = VEHICULOS[self.vehiculo].capacidad
        self.restricciones = Restricciones(capacidad=self.capacidad, r={}, l={}, theta={}, carga={})
        self.plan: list[Parada] = []
        # Persistente a nivel de env (no por-EstadoRuta): baseline_plan cachea held_karp
        # (plan) dentro de un EstadoRuta, pero _estado_ruta() se llama varias veces por
        # step con un EstadoRuta NUEVO cada vez -- sin este diccionario compartido, el
        # caché de baseline_plan nunca sobrevive entre esas llamadas y held_karp(plan) se
        # recalcula desde cero cada vez (era el costo dominante del entorno, ver HANDOFF).
        # Se limpia en `_recalendarizar()`, exactamente cuando el plan cambia de verdad.
        self._cache_estado_ruta: dict = {}
        self._llegadas_cache: Optional[list[float]] = None
        self._salidas_cache: Optional[list[float]] = None

        self.pedidos: dict[str, PedidoGenerado] = {}
        self.estado_pedido: dict[str, str] = {}
        self.slots: list[Optional[str]] = [None] * K_F
        self.slot_mostrado_en: dict[str, float] = {}
        self.rondas: dict[str, int] = {}
        self.cola_pendientes: deque[str] = deque()

        self.ganancia_acum = 0.0
        self.km_acum = 0.0
        self.km_vacios_acum = 0.0
        self.costo_tiempo_acum = 0.0
        self.penalizaciones_acum = 0.0
        self.rho_hat = RHO_HAT_INICIAL
        self.contadores = {
            "generados": 0, "entregados": 0, "rechazados": 0, "expirados": 0,
            "perdidos": 0, "cancelados": 0,
        }
        self.violaciones_frescura = 0
        self._carga_muestras: list[int] = []
        self._p_gana_muestras: list[float] = []
        self._entregas_a_tiempo = 0
        self._entregas_totales = 0

        self._eventos: list[tuple[float, int, str, Optional[str]]] = []
        self._contador_eventos = 0
        self._t_terminado = False

        # El avance inicial (hasta el primer punto de decisión) no debe cobrarse: gymnasium
        # no expone una recompensa de reset(), así que cualquier costo de tiempo que se
        # cobrara aquí quedaría en el ledger sin aparecer nunca en la suma de recompensas
        # de step() -- rompía la invariante de contabilidad por una espera "gratis" al
        # arranque que el ledger sí veía.
        self._contabilidad_activa = False
        self._agendar_siguiente_pedido()
        self._avanzar_hasta_decision()
        self._contabilidad_activa = True

        self._refrescar_mascara()
        return self._obs(), self._info()

    # ------------------------------------------------------------------ step -----

    def step(self, action: int):
        recompensa = self._aplicar_accion(int(action))
        recompensa += self._avanzar_hasta_decision()

        terminado = self.t >= self.duracion_turno_s
        truncado = False
        self._refrescar_mascara()
        return self._obs(), recompensa, terminado, truncado, self._info()

    def _refrescar_mascara(self) -> None:
        """`action_mask` se calcula UNA vez por step()/reset() (antes se recalculaba una
        vez para `_obs()` -- que hasta hace poco ni siquiera la usaba, ver más abajo -- y
        otra para `_info()`); `_obs()` e `_info()` sólo leen `self._ultima_mask`."""
        self._ultima_mask = action_mask(self._estado_ruta())

    # ------------------------------------------------------------------ acción ---

    def _carga_a_bordo(self) -> int:
        """Pedidos FÍSICAMENTE a bordo ahora mismo: ya recogidos (su parada de recogida
        salió de `self.plan`) pero todavía no entregados (su parada de entrega sigue en
        `self.plan`). Distinto de "pedidos comprometidos al plan" (que puede ser mayor:
        el plan puede tener varios pedidos por recoger, respetando capacidad en cada
        tramo de la ruta, sin que estén onboard todos a la vez)."""

        ids_por_recoger = {p.id for p in self.plan if p.tipo == "recogida"}
        return sum(1 for p in self.plan if p.tipo == "entrega" and p.id not in ids_por_recoger)

    def _travel_fn(self, a: tuple[int, int], b: tuple[int, int], t: float) -> tuple[float, float]:
        """`GridWorld.travel` pide clima explícito; sequencer.TravelFn es de 3 argumentos.
        Se cierra sobre el clima vigente (sólo cambia vía CadenaClima.avanzar, nunca en
        medio de una secuencia de llamadas de held_karp/verificar_y_calendarizar)."""
        return self.grid.travel(a, b, t, self.generador.clima.estado)

    def _estado_ruta(self) -> EstadoRuta:
        ofertas: list[Optional[OfertaCandidata]] = []
        for pid in self.slots:
            if pid is None:
                ofertas.append(None)
                continue
            p = self.pedidos[pid]
            dist_m = math.hypot(
                (self.pos[0] - p.origen[0]) * self.grid.cell_size_m,
                (self.pos[1] - p.origen[1]) * self.grid.cell_size_m,
            )
            ofertas.append(OfertaCandidata(
                id=pid, pos_recogida=p.origen, pos_entrega=p.destino, r=p.tiempo_listo_en,
                l=p.fecha_limite, theta=p.theta_frescura, carga=1,
                expira_en=self.slot_mostrado_en[pid] + EXPIRA_OFERTA_S, precio=p.precio,
                anillo=self.generador.anillo_de(dist_m),
                p_gana_estimada=self.generador.p_gana_estimada(dist_m, self.generador.n_competidores_base),
            ))
        return EstadoRuta(
            t=self.t, pos=self.pos, clima=self.generador.clima.estado, plan=self.plan,
            restricciones=self.restricciones, travel_fn=self._travel_fn, ofertas=ofertas,
            cache=self._cache_estado_ruta,
        )

    def _aplicar_accion(self, accion: int) -> float:
        """Valida SÓLO lo que la acción elegida necesita (no la máscara de las 10 acciones
        completa: esa ya se calculó -- y se recalcula, más barato, sólo una vez por step,
        en `_info()` -- para la SIGUIENTE decisión). Evita pagar 8 `eval_insertion` para
        validar una acción que a lo más necesita 1."""

        if accion == K_F:  # rechazar_todas: siempre válida
            for pid in list(self.slots):
                if pid is not None:
                    self._retirar_oferta(pid, "rechazado")
            return 0.0

        if accion == K_F + 1:  # reposicionarse
            estado = self._estado_ruta()
            holguras = holguras_frescura_plan(estado)
            if any(h < HOLGURA_MINIMA_REPOSICIONAR_S for h in holguras):
                return 0.0
            return self._reposicionar()

        pid = self.slots[accion] if accion < K_F else None
        if pid is None:
            return 0.0
        estado = self._estado_ruta()
        oferta = estado.ofertas[accion]
        if oferta.expira_en is not None and oferta.expira_en <= self.t:
            return 0.0
        _dt, _dd, factible = eval_insertion(self.plan, oferta, estado)
        if not factible:
            return 0.0

        return self._aceptar_oferta(pid)

    def _reposicionar(self) -> float:
        n = self.grid.n
        mejor, mejor_densidad = self.pos, -1.0
        for df in (-1, 0, 1):
            for dc in (-1, 0, 1):
                f, c = self.pos[0] + df, self.pos[1] + dc
                if 0 <= f < n and 0 <= c < n:
                    d = self.grid.densidad[f, c]
                    if d > mejor_densidad:
                        mejor_densidad, mejor = d, (f, c)
        if mejor == self.pos:
            return 0.0
        dt, dm = self.grid.travel(self.pos, mejor, self.t, self.generador.clima.estado)
        self.t += dt
        self.pos = mejor
        self.km_acum += dm / 1000.0
        self.km_vacios_acum += dm / 1000.0
        self.costo_tiempo_acum += self.rho_hat * (dt / 3600.0)
        return -COSTO_KM_MXN * (dm / 1000.0) - self.rho_hat * (dt / 3600.0)

    def _aceptar_oferta(self, pid: str) -> float:
        p = self.pedidos[pid]
        plan_previo = list(self.plan)
        r_previo, l_previo = dict(self.restricciones.r), dict(self.restricciones.l)
        theta_previo, carga_previo = dict(self.restricciones.theta), dict(self.restricciones.carga)

        self.plan.append(Parada(pid, "recogida", p.origen))
        self.plan.append(Parada(pid, "entrega", p.destino))
        self.restricciones.r[pid] = p.tiempo_listo_en
        self.restricciones.l[pid] = p.fecha_limite
        self.restricciones.theta[pid] = p.theta_frescura
        self.restricciones.carga[pid] = 1

        # TOPE DURO K_A: action_mask ya no ofrece slots factibles con el plan lleno (§
        # feasibility.K_A_MAXIMO), así que esto nunca debería dispararse -- es la red de
        # seguridad explícita que pide la tarea, no la única línea de defensa.
        assert len(self.plan) // 2 <= K_A_MAXIMO, (
            f"plan activo con {len(self.plan) // 2} pedidos, excede K_A_MAXIMO={K_A_MAXIMO}"
        )

        if not self._recalendarizar():
            # La guardia de tiempo de held_karp (25ms) puede impedir confirmar un horario
            # exacto para el plan con el pedido nuevo, aunque la inserción barata (más
            # optimista: sólo prueba insertar en el orden ya fijo) haya dicho que sí cabía.
            # Revertir aquí es obligatorio: sin esto, el plan queda con paradas pero sin
            # horario (`_salidas_cache=None`), `_proximo_evento_nodo` deja de encontrar
            # eventos de nodo, y el vehículo se congela para el resto del episodio (bug
            # real encontrado al medir este bloque, ver reports/HANDOFF.md).
            self.plan = plan_previo
            self.restricciones.r, self.restricciones.l = r_previo, l_previo
            self.restricciones.theta, self.restricciones.carga = theta_previo, carga_previo
            self._recalendarizar()  # el plan previo ya era factible; no debería volver a fallar
            self.estado_pedido[pid] = "perdido"
            self.contadores["perdidos"] += 1
            return 0.0

        distancia_estim = abs(self.pos[0] - p.origen[0]) + abs(self.pos[1] - p.origen[1])
        self._p_gana_muestras.append(
            self.generador.p_gana_estimada(distancia_estim * self.grid.cell_size_m, self.generador.n_competidores_base),
        )

        # "Aceptar" registra la respuesta del agente para el cierre de ronda; el pedido
        # sólo se vuelve 'asignado' de verdad si gana (ver _procesar_cierre_ronda). Se
        # retira del slot visible ya (no puede seguir "visible" mientras se decide).
        self.estado_pedido[pid] = "compitiendo"
        self.slots[self.slots.index(pid)] = None
        return 0.0

    def _retirar_oferta(self, pid: str, motivo: str) -> None:
        if pid in self.slots:
            self.slots[self.slots.index(pid)] = None
        if self.estado_pedido.get(pid) in ("visible", None):
            self.estado_pedido[pid] = motivo
            self.contadores[f"{motivo}s"] += 1
        self._liberar_slot_pendiente()

    # ------------------------------------------------------------------ eventos --

    def _agendar(self, t: float, tipo: str, pid: Optional[str]) -> None:
        self._contador_eventos += 1
        heapq.heappush(self._eventos, (t, self._contador_eventos, tipo, pid))

    def _agendar_siguiente_pedido(self) -> None:
        if self.t >= self.duracion_turno_s:
            return
        t_llegada, pedido = self.generador.siguiente_pedido(self.t)
        self.pedidos[pedido.id] = pedido
        self.contadores["generados"] += 1
        self._agendar(t_llegada, "pedido", pedido.id)

    def _recalendarizar(self) -> bool:
        """Reoptimización EXACTA completa (held_karp, camino exacto porque el plan nunca
        pasa de K_A_MAXIMO pedidos) -- se corre UNA sola vez por cambio de plan (aceptar,
        revertir tras perder, entregar/recoger), nunca por cada oferta evaluada (eso lo
        hace `insertion.mejor_insercion`, barato). Deja `self.plan` REORDENADO según el
        óptimo encontrado: de ahí en adelante el plan siempre está en su orden vigente, y
        tanto la inserción barata como el evento de nodo pueden asumirlo (parada 0 = la
        próxima) sin volver a preguntarle a held_karp.

        Devuelve False si no pudo confirmar un horario (held_karp topó con su guardia de
        tiempo de 25ms, o el plan es genuinamente infactible). El llamador es responsable
        de reaccionar -- normalmente revirtiendo el cambio que se acaba de hacer (ver
        `_aceptar_oferta`): dejar `self.plan` con paradas pero sin horario congela el
        vehículo para siempre (`_proximo_evento_nodo` nunca vuelve a encontrar un evento)."""

        # Invalidar SIEMPRE primero: si algo falla abajo, `_proximo_evento_nodo` debe ver
        # que no hay horario válido (None) en vez de reusar uno viejo que ya no corresponde
        # al `self.plan` actual -- un horario viejo puede apuntar a una parada ya visitada
        # y cuyo tiempo no avanza, lo que cuelga el loop de eventos en un ciclo sin fin.
        self._llegadas_cache = None
        self._salidas_cache = None

        if not self.plan:
            return True
        stops = [{"id": p.id, "tipo": p.tipo, "pos": p.pos} for p in self.plan]
        orden, _tiempo, _dist, _exacto, _eval = held_karp(
            stops, self.t, self.pos, self._travel_fn, self.restricciones,
        )
        if orden is None:
            return False
        self.plan = [self.plan[i] for i in orden]
        resultado = verificar_y_calendarizar(
            list(range(len(self.plan))), self.plan, self.t, self.pos, self._travel_fn, self.restricciones,
        )
        if resultado is None:
            return False
        self._llegadas_cache, self._salidas_cache, _dist_total = resultado
        return True

    def _proximo_evento_nodo(self) -> Optional[float]:
        """Instante en que el vehículo queda libre para la siguiente parada: es la SALIDA
        de la próxima parada del plan, no la llegada -- en una recogida, salida ya incluye
        la espera obligatoria por preparación (max(llegada, r_i)); usar llegada saltaría esa
        espera. `self.plan` siempre está en su orden vigente (`_recalendarizar` lo deja
        así), así que la próxima parada es siempre el índice 0."""
        if not self.plan or self._salidas_cache is None:
            return None
        return self._salidas_cache[0]

    def _avanzar_hasta_decision(self) -> float:
        """Procesa eventos hasta que quede al menos un slot para mostrar una oferta nueva,
        o se acabe el turno. Devuelve la recompensa acumulada de todos los eventos
        procesados en el camino (entregas, costos de tiempo/distancia)."""

        t_inicio = self.t
        recompensa = 0.0
        iteraciones = 0
        while self.t < self.duracion_turno_s:
            iteraciones += 1
            if iteraciones > 10_000:
                # Red de seguridad: no debería hacer falta (cada evento procesado o bien
                # avanza self.t o bien libera un slot y sale del loop), pero un bug futuro
                # aquí sería un cuelgue silencioso en vez de un error visible.
                self.t = self.duracion_turno_s
                break
            t_nodo = self._proximo_evento_nodo()
            proximo_evento_es_nodo = t_nodo is not None and (not self._eventos or t_nodo <= self._eventos[0][0])

            if proximo_evento_es_nodo:
                # Las llegadas a nodo (recogida/entrega física) nunca son punto de
                # decisión: son física del plan ya comprometido, no algo que el agente
                # decida. Se procesan y se sigue de largo dentro del mismo step().
                recompensa += self._procesar_llegada_nodo(t_nodo)
                continue

            if not self._eventos:
                self.t = self.duracion_turno_s
                break

            t_evt, _seq, tipo, pid = heapq.heappop(self._eventos)
            if t_evt > self.duracion_turno_s:
                heapq.heappush(self._eventos, (t_evt, _seq, tipo, pid))
                self.t = self.duracion_turno_s
                break

            dt = t_evt - self.t
            if dt > 0:
                costo = self.rho_hat * (dt / 3600.0)
                if self._contabilidad_activa:
                    recompensa -= costo
                    self.costo_tiempo_acum += costo
            self.t = t_evt

            if tipo == "pedido":
                recompensa += self._procesar_llegada_pedido(pid)
            elif tipo == "expira_oferta":
                self._procesar_expiracion(pid)
            elif tipo == "cierra_ronda":
                recompensa += self._procesar_cierre_ronda(pid)

            if any(s is None for s in self.slots) and self.cola_pendientes:
                self._liberar_slot_pendiente()

            # UNA decisión por cierre de ronda, no por oferta: las llegadas de pedido y las
            # expiraciones se procesan en el mismo step() sin devolver el control al
            # agente -- llegan mucho más seguido que los cierres de ronda (45s) y antes
            # generaban una época de decisión cada una, por eso la primera entrega caía
            # hasta el paso ~1500 de un turno. Sólo "cierra_ronda" (cuando de verdad puede
            # haber algo nuevo que decidir: se liberó un slot, se resolvió un pedido) para
            # el loop y le devuelve el turno al agente.
            if tipo == "cierra_ronda":
                break

        self._actualizar_rho_hat(recompensa, self.t - t_inicio)
        return recompensa

    def _procesar_llegada_pedido(self, pid: str) -> float:
        self.estado_pedido[pid] = "buscando"
        if None in self.slots:
            self._mostrar_oferta(pid)
        else:
            self._encolar_o_expirar(pid)
        self._agendar_siguiente_pedido()
        return 0.0

    def _encolar_o_expirar(self, pid: str) -> None:
        if len(self.cola_pendientes) >= MAX_COLA_PENDIENTES:
            self.estado_pedido[pid] = "expirado"
            self.contadores["expirados"] += 1
            return
        self.cola_pendientes.append(pid)

    def _mostrar_oferta(self, pid: str) -> None:
        idx = self.slots.index(None)
        self.slots[idx] = pid
        self.slot_mostrado_en[pid] = self.t
        self.estado_pedido[pid] = "visible"
        self.rondas[pid] = self.rondas.get(pid, 0) + 1
        self._agendar(self.t + EXPIRA_OFERTA_S, "expira_oferta", pid)
        self._agendar(self.t + DURACION_RONDA_S, "cierra_ronda", pid)

    def _liberar_slot_pendiente(self) -> None:
        while None in self.slots and self.cola_pendientes:
            pid = self.cola_pendientes.popleft()
            if self.estado_pedido.get(pid) == "buscando":
                self._mostrar_oferta(pid)

    def _procesar_expiracion(self, pid: str) -> None:
        if self.estado_pedido.get(pid) == "visible":
            if pid in self.slots:
                self.slots[self.slots.index(pid)] = None
            self.estado_pedido[pid] = "expirado_pendiente"  # ronda sigue viva vía competidores

    _ESTADOS_TERMINALES = frozenset({
        "rechazado", "expirado", "perdido", "cancelado", "entregado", "asignado",
    })

    def _procesar_cierre_ronda(self, pid: str) -> float:
        p = self.pedidos[pid]
        estado_actual = self.estado_pedido.get(pid)
        if estado_actual in self._ESTADOS_TERMINALES:
            # El agente ya decidió (rechazó explícitamente, o el pedido ya se resolvió por
            # otra vía). Este cierre de ronda quedó agendado desde que se mostró la oferta;
            # no debe resucitar un pedido ya terminado -- re-encolarlo aquí era el bug que
            # inflaba "rechazados" por encima de "generados" (ver HANDOFF).
            return 0.0
        respuestas: list[tuple[str, float, float]] = []
        if estado_actual == "compitiendo":
            dist = math.hypot(
                (self.pos[0] - p.origen[0]) * self.grid.cell_size_m,
                (self.pos[1] - p.origen[1]) * self.grid.cell_size_m,
            )
            respuestas.append(("agente", dist, self.t))

        dif_falsa = self.generador.iniciar_difusion(p, self.rondas.get(pid, 1), self.t - DURACION_RONDA_S)
        ganador, _perdedores = self.generador.resolver_ronda(p, dif_falsa, respuestas)

        if ganador == "agente":
            self.estado_pedido[pid] = "asignado"
            return 0.0

        if estado_actual == "compitiendo":
            # El agente comprometió capacidad y perdió: se revierte del plan.
            self._revertir_del_plan(pid)
            self.contadores["perdidos"] += 1
            self.estado_pedido[pid] = "perdido"
            return 0.0

        if ganador is not None:
            # Un competidor ganó y el agente ni compitió: el pedido deja de ser nuestro.
            self.estado_pedido[pid] = "perdido"
            self.contadores["perdidos"] += 1
            return 0.0

        # Nadie aceptó esta ronda.
        ronda = self.rondas.get(pid, 1)
        if ronda >= MAX_RONDAS:
            self.estado_pedido[pid] = "cancelado"
            self.contadores["cancelados"] += 1
            if pid in self.slots:
                self.slots[self.slots.index(pid)] = None
            return 0.0

        # sin_respuesta -> siguiente ronda: se re-encola para que le toque slot de nuevo.
        if pid in self.slots:
            self.slots[self.slots.index(pid)] = None
        self.estado_pedido[pid] = "buscando"
        self._encolar_o_expirar(pid)
        return 0.0

    def _revertir_del_plan(self, pid: str) -> None:
        self.plan = [p for p in self.plan if p.id != pid]
        self.restricciones.r.pop(pid, None)
        self.restricciones.l.pop(pid, None)
        self.restricciones.theta.pop(pid, None)
        self.restricciones.carga.pop(pid, None)
        self._recalendarizar()

    def _procesar_llegada_nodo(self, t_salida: float) -> float:
        parada = self.plan[0]
        p = self.pedidos[parada.id]
        dt = t_salida - self.t
        if dt > 0:
            costo_tiempo = self.rho_hat * (dt / 3600.0)
            recompensa = -costo_tiempo
            self.costo_tiempo_acum += costo_tiempo
        else:
            recompensa = 0.0
        self.t = t_salida
        dm = (abs(self.pos[0] - parada.pos[0]) + abs(self.pos[1] - parada.pos[1])) * self.grid.cell_size_m
        self.km_acum += dm / 1000.0
        self.pos = parada.pos
        recompensa -= COSTO_KM_MXN * (dm / 1000.0)

        if parada.tipo == "recogida":
            # A partir de aquí el pedido sigue en el plan SÓLO con su parada de entrega
            # (ver sequencer.py: pedidos "ya recogidos" no llevan restricción de
            # precedencia). La frescura (T_entrega - S_recogida <= theta) se dobla en una
            # fecha límite equivalente: S_recogida ya es un hecho fijo (t_salida), así que
            # el límite efectivo de entrega es min(l_i, t_salida + theta_i). Sin este
            # pliegue, el chequeo de holgura de reposicionarse (feasibility.py) no tendría
            # de dónde leer la frescura de un pedido ya recogido.
            theta = self.restricciones.theta.get(parada.id)
            if theta is not None:
                limite_actual = self.restricciones.l.get(parada.id)
                limite_frescura = t_salida + theta
                self.restricciones.l[parada.id] = (
                    min(limite_actual, limite_frescura) if limite_actual is not None else limite_frescura
                )
                self.restricciones.theta[parada.id] = None
        else:
            entregado_a_tiempo = t_salida <= p.fecha_limite + 1e-6
            self._entregas_totales += 1
            self._entregas_a_tiempo += int(entregado_a_tiempo)
            if not entregado_a_tiempo:
                retraso_min = (t_salida - p.fecha_limite) / 60.0
                penalizacion = PSI_RETRASO_MXN_MIN * retraso_min
                recompensa -= penalizacion
                self.penalizaciones_acum += penalizacion
            recompensa += p.precio
            self.ganancia_acum += p.precio
            self.estado_pedido[parada.id] = "entregado"
            self.contadores["entregados"] += 1

        self.plan = self.plan[1:]
        if parada.tipo == "entrega":
            for k in ("r", "l", "theta", "carga"):
                getattr(self.restricciones, k).pop(parada.id, None)

        self._carga_muestras.append(self._carga_a_bordo())

        self._recalendarizar()
        return recompensa

    def _actualizar_rho_hat(self, recompensa: float, dt: float) -> None:
        # Media móvil de la tasa REALIZADA (estilo R-learning): rho_hat_nuevo = (1-alfa)*
        # rho_hat + alfa*(recompensa/dt_horas) del tramo que se acaba de simular. dt=0 no
        # aporta información de tasa (nada transcurrió) y se ignora.
        if dt <= 0:
            return
        tasa_realizada = recompensa / (dt / 3600.0)
        self.rho_hat = (1 - ALFA_RHO_HAT) * self.rho_hat + ALFA_RHO_HAT * tasa_realizada

    # ------------------------------------------------------------------ obs/info -

    def _obs(self) -> np.ndarray:
        clima_actual = self.generador.clima.estado
        propio = {
            "x_norm": self.pos[0] / max(self.grid.n - 1, 1),
            "y_norm": self.pos[1] / max(self.grid.n - 1, 1),
            "carga_frac": self._carga_a_bordo() / max(self.capacidad, 1),
            "t_transcurrido_norm": self.t / self.duracion_turno_s,
            "t_restante_norm": max(0.0, self.duracion_turno_s - self.t) / self.duracion_turno_s,
            "rho_hat_norm": self.rho_hat / 200.0,
            "ganancia_acum_norm": self.ganancia_acum / 1000.0,
            "km_acum_norm": self.km_acum / 100.0,
            "clima": clima_actual,
            "densidad_local": self.grid.densidad_local(self.pos) / max(self.grid.densidad.max(), 1e-9),
        }

        ids_con_recogida_pendiente = {pp.id for pp in self.plan if pp.tipo == "recogida"}
        plan_items = []
        vistos: set[str] = set()
        for parada in self.plan:
            if parada.id in vistos:
                continue
            vistos.add(parada.id)
            p = self.pedidos[parada.id]
            plan_items.append({
                "delta_origen_x": (p.origen[0] - self.pos[0]) / self.grid.n,
                "delta_origen_y": (p.origen[1] - self.pos[1]) / self.grid.n,
                "delta_destino_x": (p.destino[0] - self.pos[0]) / self.grid.n,
                "delta_destino_y": (p.destino[1] - self.pos[1]) / self.grid.n,
                "tarifa_norm": p.precio / 100.0,
                "holgura_frescura_norm": p.theta_frescura / 1800.0,
                "holgura_fecha_limite_norm": (p.fecha_limite - self.t) / 3600.0,
                "r_menos_t_norm": (p.tiempo_listo_en - self.t) / 600.0,
                "recogido": 0.0 if parada.id in ids_con_recogida_pendiente else 1.0,
                "app_idx_norm": p.app.value / 3.0,
            })
            if len(plan_items) >= K_A:
                break

        ofertas_items: list[Optional[dict]] = []
        for i, pid in enumerate(self.slots):
            if pid is None:
                ofertas_items.append(None)
                continue
            p = self.pedidos[pid]
            dist_m = math.hypot(
                (self.pos[0] - p.origen[0]) * self.grid.cell_size_m,
                (self.pos[1] - p.origen[1]) * self.grid.cell_size_m,
            )
            dt_dir, dd_dir = self.grid.travel(self.pos, p.origen, self.t, clima_actual)
            _dt2, dd2 = self.grid.travel(p.origen, p.destino, self.t, clima_actual)
            km_total = max((dd_dir + dd2) / 1000.0, 1e-6)
            anillo = self.generador.anillo_de(dist_m)
            p_gana = self.generador.p_gana_estimada(dist_m, self.generador.n_competidores_base)
            ofertas_items.append({
                "delta_origen_x": (p.origen[0] - self.pos[0]) / self.grid.n,
                "delta_origen_y": (p.origen[1] - self.pos[1]) / self.grid.n,
                "delta_destino_x": (p.destino[0] - self.pos[0]) / self.grid.n,
                "delta_destino_y": (p.destino[1] - self.pos[1]) / self.grid.n,
                "tarifa_norm": p.precio / 100.0,
                "tarifa_por_km": p.precio / km_total / 20.0,
                "delta_t_norm": dt_dir / 1800.0,
                "delta_dist_norm": dd_dir / 5000.0,
                "tasa_marginal_norm": (p.precio / max(dt_dir, 1.0)) * 3600.0 / 200.0,
                "anillo_norm": anillo / 3.0,
                "p_gana_estimada": p_gana,
                "r_menos_t_norm": (p.tiempo_listo_en - self.t) / 600.0,
                "segundos_para_expirar_norm": max(0.0, self.slot_mostrado_en[pid] + EXPIRA_OFERTA_S - self.t) / EXPIRA_OFERTA_S,
                "factible": float(self._ultima_mask[i]),
            })

        return self._constructor.construir(propio, plan_items, ofertas_items).copy()

    def _info(self) -> dict:
        horas = max(self.t / 3600.0, 1e-9)
        pedidos_h = self.contadores["entregados"] / horas
        rho_actual = (self.ganancia_acum - COSTO_KM_MXN * self.km_acum) / horas
        tasa_aceptacion = (
            self.contadores["entregados"] + self.contadores["perdidos"]
        ) / max(self.contadores["generados"], 1)
        return {
            "rho_actual": rho_actual,
            "aceptacion": tasa_aceptacion,
            "entregados": self.contadores["entregados"],
            "km": self.km_acum,
            "km_vacios": self.km_vacios_acum,
            "puntualidad": self._entregas_a_tiempo / max(self._entregas_totales, 1),
            "violaciones_frescura": self.violaciones_frescura,
            "factor_agrupamiento": (sum(self._carga_muestras) / len(self._carga_muestras)) if self._carga_muestras else 1.0,
            "p_gana_promedio": (sum(self._p_gana_muestras) / len(self._p_gana_muestras)) if self._p_gana_muestras else 0.0,
            "pedidos_generados": self.contadores["generados"],
            "pedidos_entregados": self.contadores["entregados"],
            "pedidos_rechazados": self.contadores["rechazados"],
            "pedidos_expirados": self.contadores["expirados"],
            "pedidos_perdidos": self.contadores["perdidos"],
            "pedidos_cancelados": self.contadores["cancelados"],
            "carga_actual": self._carga_a_bordo(),
            "capacidad_q": self.capacidad,
            "ledger": {
                "ingreso": self.ganancia_acum,
                "costo_distancia": COSTO_KM_MXN * self.km_acum,
                "penalizaciones": self.penalizaciones_acum,
                "costo_tiempo": self.costo_tiempo_acum,
            },
            "action_mask": self._ultima_mask,
            "pedidos_h": pedidos_h,
        }


def _bench(n_entornos: int = 16, pasos_por_entorno: int = 200) -> None:
    """`python -m vygo.env --bench`: mide steps/s agregados sobre `n_entornos` instancias
    de VygoEnv corridas SECUENCIALMENTE (sin multiproceso, por presupuesto de tiempo -- ver
    reports/HANDOFF.md). Objetivo de ai/CLAUDE.md: >=3000 steps/s con 16 entornos."""

    import time

    import numpy as np

    rng = np.random.default_rng(0)
    total_pasos = 0
    t0 = time.perf_counter()
    for seed in range(n_entornos):
        env = VygoEnv(nivel="L0", m_comercios=50)
        obs, info = env.reset(seed=seed)
        for _ in range(pasos_por_entorno):
            mask = info["action_mask"]
            validas = np.flatnonzero(mask)
            accion = int(rng.choice(validas)) if len(validas) else env.action_space.sample()
            obs, _r, terminado, truncado, info = env.step(accion)
            total_pasos += 1
            if terminado or truncado:
                break
    dt = time.perf_counter() - t0
    steps_s = total_pasos / dt
    objetivo = 3000.0
    estado = "OK" if steps_s >= objetivo else "FUERA DE OBJETIVO"
    print(
        f"VygoEnv bench: {n_entornos} entornos x hasta {pasos_por_entorno} pasos, "
        f"secuencial (no paralelo). {total_pasos} pasos en {dt:.2f}s -> {steps_s:.1f} steps/s "
        f"(objetivo >={objetivo:.0f} con 16 entornos) [{estado}]",
    )


if __name__ == "__main__":
    import sys

    if "--bench" in sys.argv:
        _bench()
    else:
        print("Uso: python -m vygo.env --bench")
