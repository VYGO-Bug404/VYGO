import type { RespuestaDecidir, Politica } from '@/lib/vygoAgent'
import type { Order } from '@/types/order'
import { useDriverStore } from '@/stores/driver.store'
import { useAuthStore } from '@/stores/auth.store'

const AGENT_URL = import.meta.env.VITE_AGENT_URL || 'https://vygo-backend.onrender.com'
const TIMEOUT_MS = 12000
// Tasa de referencia MTY cuando el repartidor aún no ha completado pedidos
const BASELINE_RHO_MXN_H = 120

// ─── Helpers ─────────────────────────────────────────────────────────────────

function isoNow(offsetMin = 0) {
  return new Date(Date.now() + offsetMin * 60_000).toISOString()
}

function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

function orderToOferta(offer: Order) {
  // theta_frescura_min: rango del backend 25-35 min, basado en estimatedMinutes
  const theta = Math.min(35, Math.max(25, Math.round(25 + (offer.estimatedMinutes ?? 10) * 0.4)))
  // espera cocina: 3-6.5 min variable por distancia
  const cocina = Math.round(3 + (offer.distanceKm ?? 2) * 0.5)
  // surge activo si el pedido viene de La Lucha / Barrio Antiguo (precio ≥ $80)
  const isSurge = offer.earnings >= 80 && offer.pickup.neighborhood === 'Centro'

  return {
    oferta_id: offer.id,
    pedido_id: offer.id,
    app: offer.platform,
    origen: { lat: offer.pickup.lat, lon: offer.pickup.lng },
    destino: { lat: offer.dropoff.lat, lon: offer.dropoff.lng },
    precio_mxn: offer.earnings,
    listo_estimado_en: isoNow(cocina),
    limite_en: isoNow(90),
    theta_frescura_min: theta,
    anillo: 1,
    ...(isSurge ? { contexto: { tipo_producto: 'caliente', surge: true } } : {}),
  }
}

function orderToPlanActivo(order: Order) {
  return {
    pedido_id: order.id,
    app: order.platform,
    estado: order.status === 'picked_up' ? 'en_camino' : 'asignado',
    origen: { lat: order.pickup.lat, lon: order.pickup.lng },
    destino: { lat: order.dropoff.lat, lon: order.dropoff.lng },
    listo_en: isoNow(2),
    limite_en: isoNow(60),
    theta_frescura_min: 25,
    recogido: order.status === 'picked_up',
  }
}

// ─── Fallback B2: regla de umbral local con geometría visible ─────────────────
function b2Fallback(offer: Order, rhoActual: number, posicion?: { lat: number; lon: number }): RespuestaDecidir {
  const pDriver = posicion ?? { lat: 25.6714, lon: -100.3094 }
  const d1 = haversineM(pDriver.lat, pDriver.lon, offer.pickup.lat, offer.pickup.lng) * 1.35
  const d2 = haversineM(offer.pickup.lat, offer.pickup.lng, offer.dropoff.lat, offer.dropoff.lng) * 1.35
  const deltaDistancia = Number((d1 + d2).toFixed(1))
  const deltaTiempo = Math.max(5, Math.round((deltaDistancia / 28) * 60 + 5))
  const tarifa = offer.earnings
  const costoMarginal = Number((deltaDistancia * 2.5 + deltaTiempo * 0.5).toFixed(2))
  const gananciaNeta = Number((tarifa - costoMarginal).toFixed(2))
  let tasaMarginal = deltaTiempo > 0 ? (gananciaNeta / (deltaTiempo / 60)) : 0
  tasaMarginal = Math.min(Math.max(tasaMarginal, 0), 450)
  const umbralSuperado = tasaMarginal > rhoActual
  const ajuste = rhoActual * 0.08

  const coords: [number, number][] = [
    [pDriver.lon, pDriver.lat],
    [pDriver.lon + (offer.pickup.lng - pDriver.lon) * 0.4, pDriver.lat + (offer.pickup.lat - pDriver.lat) * 0.4],
    [offer.pickup.lng, offer.pickup.lat],
    [offer.pickup.lng + (offer.dropoff.lng - offer.pickup.lng) * 0.5, offer.pickup.lat + (offer.dropoff.lat - offer.pickup.lat) * 0.5],
    [offer.dropoff.lng, offer.dropoff.lat],
  ]

  return {
    version: '1.0',
    generado_en: new Date().toISOString(),
    politica: 'B2_umbral',
    latencia_ms: 0,
    decisiones: [{
      oferta_id: offer.id,
      pedido_id: offer.id,
      app: offer.platform,
      decision: umbralSuperado ? 'aceptar' : 'rechazar',
      prioridad: 1,
      confianza: Math.min(0.95, Math.abs(tasaMarginal - rhoActual) / Math.max(rhoActual, 1) + 0.5),
      economia: {
        tarifa_mxn: tarifa,
        delta_tiempo_min: deltaTiempo,
        delta_distancia_km: deltaDistancia,
        costo_marginal_mxn: costoMarginal,
        ganancia_neta_mxn: gananciaNeta,
        tasa_marginal_mxn_h: Math.round(tasaMarginal),
        rho_actual_mxn_h: rhoActual,
        ajuste_aprendido_mxn_h: Math.round(ajuste),
        umbral_superado: umbralSuperado,
      },
      riesgo: {
        holgura_frescura_min: 15,
        holgura_limite_min: 20,
        prob_entrega_a_tiempo: 0.90,
        p_gana: 0.75,
        anillo: 1,
      },
      factible: true,
      motivo_infactible: null,
      explicacion_corta: umbralSuperado
        ? `+$${Math.round(tasaMarginal)}/h vs tu $${Math.round(rhoActual)}/h`
        : `$${Math.round(tasaMarginal)}/h < tu $${Math.round(rhoActual)}/h`,
      explicacion: umbralSuperado
        ? `Acepta: paga a $${Math.round(tasaMarginal)}/h contra tu promedio de $${Math.round(rhoActual)}/h. Agrega ${deltaDistancia.toFixed(1)} km y ${deltaTiempo} min.`
        : `Rechaza: solo paga a $${Math.round(tasaMarginal)}/h y tu promedio actual es $${Math.round(rhoActual)}/h. No conviene.`,
    }],
    plan: {
      viaje_id: `plan-${offer.id}`,
      paradas: [
        {
          orden: 1,
          tipo: 'recoleccion',
          pedido_id: offer.id,
          app: offer.platform,
          punto: { lat: offer.pickup.lat, lon: offer.pickup.lng },
          direccion: offer.pickup.address,
          eta: isoNow(Math.max(2, Math.round((d1 / 28) * 60))),
          eta_min: Math.max(2, Math.round((d1 / 28) * 60)),
          espera_estimada_min: 3,
          holgura_frescura_min: 25,
          estado: 'pendiente',
        },
        {
          orden: 2,
          tipo: 'entrega',
          pedido_id: offer.id,
          app: offer.platform,
          punto: { lat: offer.dropoff.lat, lon: offer.dropoff.lng },
          direccion: offer.dropoff.address,
          eta: isoNow(deltaTiempo),
          eta_min: deltaTiempo,
          holgura_frescura_min: 20,
          estado: 'pendiente',
        },
      ],
      geometria: { type: 'LineString', coordinates: coords },
      resumen: {
        paradas_totales: 2,
        pedidos_a_bordo: 1,
        distancia_km: deltaDistancia,
        duracion_min: deltaTiempo,
        ingreso_mxn: tarifa,
        costo_mxn: costoMarginal,
        tasa_proyectada_mxn_h: Math.round(tasaMarginal),
        optimo_exacto: true,
        secuencias_evaluadas: 2,
      },
    },
    telemetria: {
      rho_actual_mxn_h: rhoActual,
      ganancia_turno_mxn: 0,
      pedidos_entregados: 0,
      puntualidad: 1,
      km_por_pedido: deltaDistancia,
      factor_agrupamiento: 1,
      utilizacion: 0.7,
    },
    alertas: [],
    evento_activo: null,
  }
}

// ─── Función principal con cascada ───────────────────────────────────────────
export async function decidir(
  offer: Order,
  rhoActual: number,
  posicion?: { lat: number; lon: number },
  activeOrders: Order[] = [],
): Promise<RespuestaDecidir & { _source: 'agent' | 'b2_fallback' | 'static' }> {
  // Usar baseline cuando el turno aún no tiene entregas — evita comparar contra $0/h
  const effectiveRho = rhoActual > 0 ? rhoActual : BASELINE_RHO_MXN_H

  if (AGENT_URL) {
    try {
      const driverStore = useDriverStore.getState()
      const authStore = useAuthStore.getState()

      const shiftStartedAt = driverStore.shiftStartedAt
      const minutosTranscurridos = shiftStartedAt
        ? Math.floor((Date.now() - shiftStartedAt.getTime()) / 60_000)
        : 0
      const TURNO_TOTAL_MIN = 360 // 6h default
      const minutosRestantes = Math.max(0, TURNO_TOTAL_MIN - minutosTranscurridos)

      const DEMO_USER_ID = 'b9acb1bb-ee96-59c0-9e84-31f29368c97b'
      const targetUserId = (authStore.userId && authStore.userId !== 'driver-local')
        ? authStore.userId
        : DEMO_USER_ID

      let effectivePos = posicion
      if (!effectivePos) {
        try {
          const raw = localStorage.getItem('vygo-last-position')
          if (raw) {
            const p = JSON.parse(raw)
            const lat = typeof p.lat === 'number' ? p.lat : undefined
            const lon = typeof p.lon === 'number' ? p.lon : (typeof p.lng === 'number' ? p.lng : undefined)
            if (lat !== undefined && lon !== undefined) effectivePos = { lat, lon }
          }
        } catch {}
      }
      if (!effectivePos) effectivePos = { lat: 25.6714, lon: -100.3094 }

      const body = {
        version: '1.0',
        politica: 'HIBRIDO',
        repartidor: {
          id: targetUserId,
          posicion: effectivePos,
          vehiculo: driverStore.driver.vehicle.type ?? 'moto',
          capacidad: 3,
          minutos_turno_transcurridos: minutosTranscurridos,
          minutos_turno_restantes: minutosRestantes,
          ganancia_turno_mxn: driverStore.todayEarnings,
          km_recorridos: 0,
          rho_actual_mxn_h: effectiveRho,
        },
        plan_activo: activeOrders.map(orderToPlanActivo),
        ofertas: [orderToOferta(offer)],
        contexto: {
          clima: 'normal',
          // Activa surge si alguna oferta viene de zona centro con precio ≥ $80
          evento_activo: offer.earnings >= 80 && offer.pickup.neighborhood === 'Centro'
            ? 'surge'
            : null,
        },
      }

      const res = await Promise.race([
        fetch(`${AGENT_URL}/decidir`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('timeout')), TIMEOUT_MS)
        ),
      ])

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: RespuestaDecidir = await res.json()
      console.log(
        `%c[VYGO Agent] ✅ ${data.politica ?? 'HÍBRIDO'} · ${data.latencia_ms}ms · ${data.decisiones[0]?.decision} · ${data.decisiones[0]?.explicacion_corta}`,
        'color:#6FA800;font-weight:bold'
      )
      // Sync live telemetria from backend into driver store
      if (data.telemetria) {
        const { useDriverStore } = await import('@/stores/driver.store')
        useDriverStore.getState().syncTelemetria(data.telemetria)
      }
      return { ...data, _source: 'agent' }
    } catch (err) {
      console.warn('[VYGO Agent] caída a B2:', err)
    }
  }

  const source = AGENT_URL ? 'b2_fallback' : 'static'
  return { ...b2Fallback(offer, effectiveRho, posicion), _source: source }
}

export function politicaLabel(p: Politica): string {
  const labels: Record<string, string> = {
    HIBRIDO: 'Agente Híbrido',
    PPO: 'Agente RL',
    agente_ppo: 'Agente RL',
    agente_bc: 'Agente BC',
    B2_umbral: 'Regla umbral',
    B2: 'Regla umbral',
    B1_simple: 'Simple',
    B1: 'Simple',
  }
  return labels[p] ?? p
}

export async function obtenerRutaAstar(
  origen: { lat: number; lon?: number; lng?: number },
  destinos: { lat: number; lon?: number; lng?: number }[]
): Promise<{ coordinates: [number, number][]; distanceKm: number; durationMin: number } | null> {
  if (!destinos || destinos.length === 0) return null
  const pOrig = { lat: origen.lat, lon: (origen.lon ?? origen.lng) as number }
  const pDests = destinos.map((d) => ({ lat: d.lat, lon: (d.lon ?? d.lng) as number }))

  const targetUrl = AGENT_URL || 'https://vygo-backend.onrender.com'
  try {
    const res = await Promise.race([
      fetch(`${targetUrl}/ruteo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ origen: pOrig, destinos: pDests }),
      }),
      new Promise<never>((_, reject) => setTimeout(() => reject(new Error('timeout')), 5000)),
    ])
    if (res.ok) {
      const data = await res.json()
      if (data.geometria?.coordinates && data.geometria.coordinates.length >= 2) {
        return {
          coordinates: data.geometria.coordinates,
          distanceKm: data.distancia_km,
          durationMin: data.duracion_min,
        }
      }
    }
  } catch (err) {
    console.warn('[agent.service] /ruteo fallback a interpolación local:', err)
  }

  // Fallback local interpolado con curvatura suave para que el mapa NUNCA quede vacío
  const coords: [number, number][] = [[pOrig.lon, pOrig.lat]]
  let distKm = 0
  let durMin = 0
  let prev = pOrig
  for (const d of pDests) {
    const dKm = haversineM(prev.lat, prev.lon, d.lat, d.lon) * 1.35
    distKm += dKm
    durMin += Math.max(2, Math.round((dKm / 28) * 60))
    // Puntos de interpolación intermedia para suavizar el trazado
    coords.push([prev.lon + (d.lon - prev.lon) * 0.33, prev.lat + (d.lat - prev.lat) * 0.33])
    coords.push([prev.lon + (d.lon - prev.lon) * 0.66, prev.lat + (d.lat - prev.lat) * 0.66])
    coords.push([d.lon, d.lat])
    prev = d
  }
  return {
    coordinates: coords,
    distanceKm: Number(distKm.toFixed(1)),
    durationMin: Math.round(durMin),
  }
}

