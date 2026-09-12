import type { RespuestaDecidir, Politica } from '@/lib/vygoAgent'
import type { Order } from '@/types/order'

const AGENT_URL = import.meta.env.VITE_AGENT_URL
const TIMEOUT_MS = 2000

// ─── Fallback B2: regla de umbral local ──────────────────────────────────────
function b2Fallback(offer: Order, rhoActual: number): RespuestaDecidir {
  const tarifa = offer.earnings
  const deltaTiempo = offer.extraMinutes ?? offer.estimatedMinutes
  const deltaDistancia = offer.extraDistanceKm ?? offer.distanceKm
  const costoMarginal = deltaDistancia * 2.5 // ~$2.50/km costo operativo
  const gananciaNeta = tarifa - costoMarginal
  const tasaMarginal = deltaTiempo > 0 ? (gananciaNeta / deltaTiempo) * 60 : 0
  const umbralSuperado = tasaMarginal > rhoActual
  const ajuste = rhoActual * 0.08 // ajuste conservador

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
      confianza: Math.min(0.95, Math.abs(tasaMarginal - rhoActual) / rhoActual + 0.5),
      economia: {
        tarifa_mxn: tarifa,
        delta_tiempo_min: deltaTiempo,
        delta_distancia_km: deltaDistancia,
        costo_marginal_mxn: costoMarginal,
        ganancia_neta_mxn: gananciaNeta,
        tasa_marginal_mxn_h: Math.round(tasaMarginal),
        rho_actual_mxn_h: rhoActual,
        ajuste_aprendido_mxn_h: ajuste,
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
      paradas: [],
      geometria: { type: 'LineString', coordinates: [] },
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
  posicion?: { lat: number; lon: number }
): Promise<RespuestaDecidir & { _source: 'agent' | 'b2_fallback' | 'static' }> {

  if (AGENT_URL) {
    try {
      const body = {
        version: '1.0',
        repartidor: {
          posicion: posicion ?? { lat: 25.6714, lon: -100.3094 },
          vehiculo: 'moto',
          capacidad: 2,
          rho_actual_mxn_h: rhoActual,
        },
        plan_activo: [],
        ofertas: [{
          oferta_id: offer.id,
          pedido_id: offer.id,
          app: offer.platform,
          origen: { lat: offer.pickup.lat, lon: offer.pickup.lng },
          destino: { lat: offer.dropoff.lat, lon: offer.dropoff.lng },
          precio_mxn: offer.earnings,
          anillo: 1,
          radio_metros: 1500,
          desvio_estimado_metros: (offer.extraDistanceKm ?? offer.distanceKm) * 1000,
        }],
        contexto: { clima: 'despejado', evento_activo: null },
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
      const data = await res.json()
      return { ...data, _source: 'agent' }
    } catch {
      // Caída a B2
    }
  }

  return { ...b2Fallback(offer, rhoActual), _source: AGENT_URL ? 'b2_fallback' : 'static' }
}

export function politicaLabel(p: Politica): string {
  return { agente_ppo: 'Agente RL', agente_bc: 'Agente BC', B2_umbral: 'Regla umbral', B1_simple: 'Simple' }[p]
}
