import { useState, useEffect, useRef } from 'react'
import { X, MapPin, Navigation, Zap, CheckCircle2 } from 'lucide-react'
import { useOrdersStore } from '@/stores/orders.store'
import { useRouteStore } from '@/stores/route.store'
import { useDriverStore } from '@/stores/driver.store'
import { PlatformBadge } from '@/components/PlatformBadge'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDistance, formatMinutes } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { decidir, politicaLabel } from '@/services/agent.service'
import type { RespuestaDecidir, DecisionOferta } from '@/lib/vygoAgent'
import type { Order } from '@/types/order'

const TOTAL_SECONDS = 30
const SWIPE_THRESHOLD = 75

interface NewOrderSheetProps {
  order: Order
}

export function NewOrderSheet({ order }: NewOrderSheetProps) {
  const [accepting, setAccepting] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [agentResp, setAgentResp] = useState<(RespuestaDecidir & { _source: string }) | null>(null)
  const [loading, setLoading] = useState(true)
  const [secondsLeft, setSecondsLeft] = useState(() => {
    if (!order.expiresAt) return TOTAL_SECONDS
    return Math.max(0, Math.floor((order.expiresAt.getTime() - Date.now()) / 1000))
  })
  const touchStartY = useRef<number | null>(null)
  const acceptOffer = useOrdersStore((s) => s.acceptOffer)
  const rejectOffer = useOrdersStore((s) => s.rejectOffer)
  const activeOrders = useOrdersStore((s) => s.activeOrders)
  const rhoActual = useDriverStore((s) => s.earningsPerHour)   // unified ρ source
  const setRouteGeoJSON = useRouteStore((s) => s.setRouteGeoJSON)

  // #1 — Countdown timer
  useEffect(() => {
    if (secondsLeft <= 0) { rejectOffer(); return }
    const id = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) { rejectOffer(); return 0 }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    setLoading(true)
    let pos: { lat: number; lon: number } | undefined = undefined
    try {
      const raw = localStorage.getItem('vygo-last-position')
      if (raw) {
        const p = JSON.parse(raw)
        if (typeof p.lat === 'number' && typeof p.lng === 'number') {
          pos = { lat: p.lat, lon: p.lng }
        }
      }
    } catch {}

    decidir(order, rhoActual, pos, activeOrders).then((resp) => {
      setAgentResp(resp)
      setLoading(false)
    })
  }, [order.id])

  const dec: DecisionOferta | undefined = agentResp?.decisiones[0]
  const eco = dec?.economia
  const riesgo = dec?.riesgo
  const recomienda = dec?.decision === 'aceptar'

  const addVygoGain = useDriverStore((s) => s.addVygoGain)

  // Rechazo manual — si el agente recomendó rechazar, acumula ganancia real de VYGO
  const handleReject = () => {
    if (!recomienda && eco && eco.tasa_marginal_mxn_h < eco.rho_actual_mxn_h) {
      const timeH = eco.delta_tiempo_min / 60
      const rateDiff = eco.rho_actual_mxn_h - eco.tasa_marginal_mxn_h
      const gain = Math.max(0, Math.round(rateDiff * timeH))
      addVygoGain(gain, eco.delta_distancia_km, eco.delta_tiempo_min)
    }
    rejectOffer()
  }

  // #9 — Swipe down to reject
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartY.current = e.touches[0].clientY
  }
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartY.current === null) return
    const delta = e.changedTouches[0].clientY - touchStartY.current
    if (delta > SWIPE_THRESHOLD) rejectOffer()
    touchStartY.current = null
  }

  // #6 — Accept feedback
  const handleAccept = async () => {
    setAccepting(true)
    setAccepted(true)

    // Use geometry from agent (A* real streets); fallback to straight lines
    const geo = agentResp?.plan?.geometria
    if (geo && geo.coordinates?.length > 1) {
      setRouteGeoJSON(geo)
    } else {
      let pos: [number, number] = [-100.3094, 25.6714]
      try {
        const raw = localStorage.getItem('vygo-last-position')
        if (raw) {
          const p = JSON.parse(raw)
          if (typeof p.lat === 'number' && typeof p.lng === 'number') pos = [p.lng, p.lat]
        }
      } catch {}
      setRouteGeoJSON({
        type: 'LineString',
        coordinates: [pos, [order.pickup.lng, order.pickup.lat], [order.dropoff.lng, order.dropoff.lat]],
      })
    }

    await new Promise((r) => setTimeout(r, 600))
    acceptOffer(order, agentResp?.plan)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center animate-fade-in">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={handleReject} />

      <div
        className="relative w-full max-w-[430px] bg-vygo-card rounded-t-3xl shadow-sheet animate-slide-up overflow-hidden"
        style={{ maxHeight: '94dvh' }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {/* #6 — Accept flash overlay */}
        {accepted && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-vygo-green/20 animate-fade-in pointer-events-none">
            <div className="w-20 h-20 rounded-full bg-vygo-green flex items-center justify-center shadow-lg">
              <CheckCircle2 size={40} className="text-vygo-bg" strokeWidth={2.5} />
            </div>
          </div>
        )}

        <div className="overflow-y-auto scrollbar-none" style={{ maxHeight: '94dvh' }}>
          {/* Handle + countdown timer */}
          <div className="flex flex-col items-center pt-3 pb-1 gap-2">
            <div className="w-10 h-1 rounded-full bg-vygo-border" />
            {/* #1 — Countdown bar */}
            <div className="w-full px-5">
              <div className="h-1 bg-vygo-border rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-1000 ease-linear',
                    secondsLeft > 15 ? 'bg-vygo-green' : secondsLeft > 7 ? 'bg-vygo-warning' : 'bg-vygo-danger'
                  )}
                  style={{ width: `${(secondsLeft / TOTAL_SECONDS) * 100}%` }}
                />
              </div>
              <p className={cn(
                'text-[10px] text-right mt-0.5 font-medium',
                secondsLeft > 15 ? 'text-vygo-secondary' : secondsLeft > 7 ? 'text-vygo-warning' : 'text-vygo-danger'
              )}>
                {secondsLeft}s
              </p>
            </div>
          </div>

          {/* Header: plataforma + policy badge */}
          <div className="flex items-start justify-between px-5 pt-2 pb-1">
            <div className="flex items-center gap-2 flex-wrap">
              <PlatformBadge platform={order.platform} size="lg" />
              <span className="text-xs text-vygo-secondary">#{order.orderNumber}</span>
              {agentResp && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-vygo-card-2 border border-vygo-border text-vygo-secondary">
                  {politicaLabel(agentResp.politica)}
                </span>
              )}
            </div>
            <button
              onClick={rejectOffer}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-vygo-card-2 text-vygo-secondary hover:text-vygo-white transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* ── EXPLICACIÓN DEL AGENTE (campo obligatorio para el reto) ── */}
          <div className="px-5 pt-2 pb-3">
            {loading ? (
              <div className="h-12 bg-vygo-card-2 rounded-2xl animate-pulse border border-vygo-border" />
            ) : (
              <div className={cn(
                'rounded-2xl border px-4 py-3 flex items-start gap-3',
                recomienda
                  ? 'bg-vygo-green/8 border-vygo-green/25'
                  : 'bg-vygo-danger/5 border-vygo-danger/20'
              )}>
                {recomienda
                  ? <CheckCircle2 size={18} className="text-vygo-green flex-shrink-0 mt-0.5" />
                  : <X size={18} className="text-vygo-danger flex-shrink-0 mt-0.5" />
                }
                <div>
                  <p className={cn(
                    'text-sm font-bold leading-tight',
                    recomienda ? 'text-vygo-green' : 'text-vygo-danger'
                  )}>
                    {dec?.explicacion_corta ?? (recomienda ? 'Aceptar' : 'Rechazar')}
                  </p>
                  {dec?.explicacion && (
                    <p className="text-[11px] text-vygo-secondary mt-0.5 leading-relaxed">
                      {dec.explicacion}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* ── LOS 3 NÚMEROS DEL CRITERIO (obligatorio para el reto) ── */}
          {eco && (
            <div className="px-5 pb-3">
              <div className="bg-vygo-card-2 border border-vygo-border rounded-2xl px-4 py-3">
                <p className="text-[10px] text-vygo-secondary uppercase tracking-widest mb-2">Análisis de tasa</p>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-center flex-1">
                    <p className="text-[11px] text-vygo-secondary mb-0.5">Este pedido</p>
                    <p className="text-xl font-black text-vygo-white">${eco.tasa_marginal_mxn_h}<span className="text-xs font-normal text-vygo-secondary">/h</span></p>
                  </div>
                  <div className="flex flex-col items-center gap-0.5">
                    <div className={cn(
                      'px-2 py-1 rounded-lg text-xs font-bold',
                      eco.umbral_superado ? 'bg-vygo-green/15 text-vygo-green' : 'bg-vygo-danger/15 text-vygo-danger'
                    )}>
                      {eco.umbral_superado ? '▲' : '▼'} ${Math.abs(eco.tasa_marginal_mxn_h - eco.rho_actual_mxn_h).toFixed(0)}/h
                    </div>
                    <p className="text-[9px] text-vygo-secondary">ajuste: +${eco.ajuste_aprendido_mxn_h.toFixed(0)}</p>
                  </div>
                  <div className="text-center flex-1">
                    <p className="text-[11px] text-vygo-secondary mb-0.5">Tu promedio</p>
                    <p className="text-xl font-black text-vygo-secondary">${eco.rho_actual_mxn_h}<span className="text-xs font-normal">/h</span></p>
                  </div>
                </div>
                {agentResp?.plan.resumen.optimo_exacto && (
                  <p className="text-[10px] text-vygo-secondary/60 text-center mt-2">
                    Ruta óptima exacta · {agentResp.plan.resumen.secuencias_evaluadas} secuencias evaluadas
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ── Ganancia + métricas (3 columnas, sin "A tiempo") ── */}
          <div className="px-5 pb-3">
            <div className="grid grid-cols-3 gap-2">
              <MetricPill value={formatCurrency(order.earnings)} label="Ganancia" highlight />
              <MetricPill
                value={`+${formatMinutes(eco ? eco.delta_tiempo_min : (order.extraMinutes ?? order.estimatedMinutes))}`}
                label="Tiempo extra"
              />
              <MetricPill
                value={`+${formatDistance(eco ? eco.delta_distancia_km : (order.extraDistanceKm ?? (order.pickupDistanceKm ? order.pickupDistanceKm + order.distanceKm : order.distanceKm)))}`}
                label="Desvío total"
              />
            </div>
          </div>

          {/* ── Pickup → Dropoff ── */}
          <div className="px-5 pb-3">
            <div className="bg-vygo-card-2 rounded-2xl p-4 border border-vygo-border space-y-3">
              <div className="flex gap-3">
                <div className="flex flex-col items-center gap-1">
                  <div className="w-7 h-7 rounded-full bg-vygo-warning/15 border border-vygo-warning/30 flex items-center justify-center flex-shrink-0">
                    <MapPin size={12} className="text-vygo-warning" />
                  </div>
                  <div className="w-0.5 flex-1 min-h-[16px] bg-vygo-border" />
                </div>
                <div className="flex-1 pb-3">
                  <p className="text-xs text-vygo-secondary uppercase tracking-wide font-medium mb-0.5">Recoger</p>
                  <p className="text-sm font-semibold text-vygo-white">{order.pickup.name ?? order.restaurantName}</p>
                  <p className="text-xs text-vygo-secondary">
                    {order.pickup.address} · {order.pickup.neighborhood}
                    {order.pickupDistanceKm !== undefined ? ` (a ${order.pickupDistanceKm} km de ti)` : ''}
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-vygo-green/15 border border-vygo-green/30 flex items-center justify-center flex-shrink-0">
                  <Navigation size={12} className="text-vygo-green" />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-vygo-secondary uppercase tracking-wide font-medium mb-0.5">Entregar</p>
                  <p className="text-sm font-semibold text-vygo-white">{order.dropoff.address}</p>
                  <p className="text-xs text-vygo-secondary">
                    {order.dropoff.neighborhood} · Entrega de {order.distanceKm} km
                  </p>
                </div>
              </div>
            </div>
          </div>


          {/* ── Evento activo (surge) ── */}
          {agentResp?.evento_activo && (
            <div className="px-5 pb-3">
              <div className="flex items-center gap-2 bg-vygo-warning/10 border border-vygo-warning/25 rounded-2xl px-4 py-2.5">
                <Zap size={14} className="text-vygo-warning flex-shrink-0" />
                <p className="text-xs text-vygo-warning font-semibold">
                  Surge ×{agentResp.evento_activo.multiplicador_tarifa?.toFixed(1)} en {agentResp.evento_activo.zona}
                </p>
              </div>
            </div>
          )}

          {/* ── Buttons ── */}
          <div className="px-5 pb-6 grid grid-cols-2 gap-3">
            <Button variant="destructive" size="lg" onClick={handleReject} className="h-14">
              Rechazar
            </Button>
            <Button
              variant="default"
              size="lg"
              onClick={handleAccept}
              disabled={accepting || loading}
              className={cn('h-14 transition-all duration-200', accepting && 'scale-95 opacity-80')}
            >
              {accepting ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-vygo-bg/50 border-t-vygo-bg rounded-full animate-spin" />
                  Aceptando…
                </span>
              ) : 'Aceptar'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricPill({ value, label, highlight = false }: { value: string; label: string; highlight?: boolean }) {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center rounded-xl py-3 px-1 gap-0.5 border',
      highlight ? 'bg-vygo-green/8 border-vygo-green/20' : 'bg-vygo-card-2 border-vygo-border'
    )}>
      <span className={cn('text-sm font-bold leading-tight text-center', highlight ? 'text-vygo-green' : 'text-vygo-white')}>
        {value}
      </span>
      <span className="text-[9px] text-vygo-secondary font-medium text-center leading-tight">{label}</span>
    </div>
  )
}
