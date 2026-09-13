import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ChevronRight, LogOut, TrendingUp, Clock, Package, Zap, Store, MapPin, Navigation, ExternalLink } from 'lucide-react'
import { useOrdersStore } from '@/stores/orders.store'
import { useRouteStore } from '@/stores/route.store'
import { useDriverStore } from '@/stores/driver.store'
import { obtenerRutaAstar } from '@/services/agent.service'

import { useActiveRoute } from '@/hooks/useActiveRoute'
import { useEndShift } from '@/hooks/useEndShift'
import { EndShiftConfirm } from '@/components/EndShiftConfirm'
import { MockMap } from '@/components/maps/MockMap'
import { PlatformBadge } from '@/components/PlatformBadge'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDistance, formatMinutes, formatTime, haversineKm } from '@/lib/utils'

const STATUS_LABEL: Record<string, string> = {
  heading_to_pickup: 'Llegué al restaurante',
  accepted: 'Llegué al restaurante',
  picked_up: 'Pedido entregado',
  delivered: 'Completado',
}

export function ActiveRoutePage() {
  const navigate = useNavigate()
  const activeOrders = useOrdersStore((s) => s.activeOrders)
  const advanceOrder = useOrdersStore((s) => s.advanceOrder)
  const advanceStop = useRouteStore((s) => s.advanceStop)
  const routeGeoJSON = useRouteStore((s) => s.routeGeoJSON)
  const setRouteGeoJSON = useRouteStore((s) => s.setRouteGeoJSON)
  const activeRoute = useRouteStore((s) => s.activeRoute)
  const { currentStop, nextStop, totalStops } = useActiveRoute()
  const currentStopIndex = useRouteStore((s) => s.currentStopIndex)

  const [driverPos, setDriverPos] = useState<{ lat: number; lng: number }>(() => {
    try {
      const raw = localStorage.getItem('vygo-last-position')
      if (raw) {
        const p = JSON.parse(raw)
        if (typeof p.lat === 'number' && typeof p.lng === 'number') return { lat: p.lat, lng: p.lng }
      }
    } catch {}
    return { lat: 25.6714, lng: -100.3094 }
  })

  useEffect(() => {
    if (!navigator.geolocation) return
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        setDriverPos({ lat: pos.coords.latitude, lng: pos.coords.longitude })
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 3000 }
    )
    return () => navigator.geolocation.clearWatch(id)
  }, [])

  const controllerRef = useRef<import('@/lib/mapRouteController').MapRouteController | null>(null)
  const [liveDistanceM, setLiveDistanceM] = useState<number | null>(null)

  const { tryEndShift, confirming, confirmEnd, cancelConfirm } = useEndShift()
  const todayEarnings = useDriverStore((s) => s.todayEarnings)
  const earningsPerHour = useDriverStore((s) => s.earningsPerHour)
  const shiftStartedAt = useDriverStore((s) => s.shiftStartedAt)
  const completedOrdersCount = useDriverStore((s) => s.completedOrders)

  const primaryOrder = currentStop?.order ?? activeOrders[0] ?? null
  const nextOrder = nextStop?.order ?? activeOrders[1] ?? null

  const targetCoords = currentStop
    ? currentStop.type === 'pickup'
      ? primaryOrder?.pickup
      : primaryOrder?.dropoff
    : null

  const distKmToStop = targetCoords
    ? haversineKm(driverPos.lat, driverPos.lng, targetCoords.lat, targetCoords.lng)
    : 0

  const distLabel = liveDistanceM !== null
    ? liveDistanceM < 1000
      ? `${Math.max(10, Math.round(liveDistanceM))} m`
      : `${(liveDistanceM / 1000).toFixed(1)} km`
    : distKmToStop < 1.0
      ? `${Math.max(50, Math.round(distKmToStop * 1000))} m`
      : `${distKmToStop.toFixed(1)} km`

  const minutesToStop = Math.max(1, Math.round((liveDistanceM !== null ? liveDistanceM / 1000 : distKmToStop) * 2.2))
  const etaDate = new Date(Date.now() + minutesToStop * 60000)
  const etaTimeStr = formatTime(etaDate)

  const totalRemainingKm = activeOrders.reduce((sum, o) => {
    if (o.status === 'delivered') return sum
    if (o.status === 'picked_up') return sum + o.distanceKm
    return sum + (o.pickupDistanceKm ?? 1.5) + o.distanceKm
  }, 0)

  const progressPct = totalStops > 0 ? (currentStopIndex / totalStops) * 100 : 0

  const handleAdvance = () => {
    if (primaryOrder) {
      advanceOrder(primaryOrder.id)
      advanceStop()
      controllerRef.current?.avanzar()
    }
  }

  const handleControllerAdvance = useCallback((_idx: number) => {
    if (primaryOrder) {
      advanceOrder(primaryOrder.id)
      advanceStop()
    }
  }, [primaryOrder, advanceOrder, advanceStop])

  const actionLabel = primaryOrder
    ? (STATUS_LABEL[primaryOrder.status] ?? 'Pedido entregado')
    : 'Completado'

  const destination = currentStop
    ? currentStop.type === 'pickup'
      ? primaryOrder?.pickup.address
      : primaryOrder?.dropoff.address
    : null

  if (!primaryOrder && activeOrders.length === 0) {
    const shiftMinutes = shiftStartedAt
      ? Math.floor((Date.now() - shiftStartedAt.getTime()) / 60000)
      : 0
    const shiftHours = shiftMinutes / 60

    // Proyecciones
    const proj1h = Math.round(todayEarnings + earningsPerHour)
    const proj2h = Math.round(todayEarnings + earningsPerHour * 2)

    return (
      <div
        className="flex flex-col h-full bg-vygo-bg overflow-y-auto"
        style={{ paddingTop: `max(env(safe-area-inset-top, 0px), 16px)`, paddingBottom: `max(env(safe-area-inset-bottom, 0px), 16px)` }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-4 mb-6">
          <button
            onClick={() => navigate('/')}
            className="w-9 h-9 flex items-center justify-center rounded-xl bg-vygo-card border border-vygo-border text-vygo-secondary"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <p className="text-xs text-vygo-secondary">Sin pedidos activos</p>
            <h2 className="text-base font-bold text-vygo-white">Resumen de jornada</h2>
          </div>
          <div className="ml-auto flex items-center gap-1.5 bg-vygo-green/10 border border-vygo-green/20 rounded-full px-2.5 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-vygo-green animate-pulse" />
            <span className="text-[11px] text-vygo-green font-medium">En línea</span>
          </div>
        </div>

        <div className="px-4 flex flex-col gap-4">

          {/* Ganancia principal */}
          <div className="bg-vygo-card border border-vygo-border rounded-2xl p-5 text-center">
            <p className="text-xs text-vygo-secondary uppercase tracking-widest mb-1">Ganado hoy</p>
            <p className="text-5xl font-black text-vygo-green tracking-tight">
              {formatCurrency(todayEarnings)}
            </p>
            <p className="text-sm text-vygo-secondary mt-1">
              {formatCurrency(earningsPerHour)}/hr promedio
            </p>
          </div>

          {/* Métricas de jornada */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3 flex flex-col items-center gap-1">
              <Clock size={16} className="text-vygo-secondary" />
              <p className="text-lg font-bold text-vygo-white">
                {shiftHours >= 1 ? `${shiftHours.toFixed(1)}h` : `${shiftMinutes}m`}
              </p>
              <p className="text-[10px] text-vygo-secondary text-center">Trabajado</p>
            </div>
            <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3 flex flex-col items-center gap-1">
              <Package size={16} className="text-vygo-secondary" />
              <p className="text-lg font-bold text-vygo-white">{completedOrdersCount}</p>
              <p className="text-[10px] text-vygo-secondary text-center">Entregas</p>
            </div>
            <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3 flex flex-col items-center gap-1">
              <TrendingUp size={16} className="text-vygo-secondary" />
              <p className="text-lg font-bold text-vygo-white">
                {completedOrdersCount > 0 && shiftHours > 0
                  ? (completedOrdersCount / shiftHours).toFixed(1)
                  : '—'}
              </p>
              <p className="text-[10px] text-vygo-secondary text-center">Pedidos/hr</p>
            </div>
          </div>

          {/* Proyección si sigues trabajando */}
          <div className="bg-vygo-card border border-vygo-border rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-vygo-border flex items-center gap-2">
              <Zap size={14} className="text-vygo-warning" />
              <p className="text-sm font-semibold text-vygo-white">Si sigues trabajando</p>
            </div>
            <div className="divide-y divide-vygo-border">
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm text-vygo-white font-medium">+1 hora más</p>
                  <p className="text-xs text-vygo-secondary">~{formatCurrency(earningsPerHour)} adicionales</p>
                </div>
                <p className="text-base font-bold text-vygo-green">{formatCurrency(proj1h)}</p>
              </div>
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm text-vygo-white font-medium">+2 horas más</p>
                  <p className="text-xs text-vygo-secondary">~{formatCurrency(earningsPerHour * 2)} adicionales</p>
                </div>
                <p className="text-base font-bold text-vygo-green">{formatCurrency(proj2h)}</p>
              </div>
            </div>
          </div>

          {/* Acciones */}
          <div className="flex flex-col gap-2 pt-1">
            <Button onClick={() => navigate('/')} size="lg" className="w-full h-13">
              Seguir trabajando
            </Button>
            <button
              onClick={() => tryEndShift(() => navigate('/'))}
              className="flex items-center justify-center gap-2 w-full h-12 rounded-2xl border border-vygo-danger/30 bg-vygo-danger/5 text-vygo-danger text-sm font-semibold hover:bg-vygo-danger/10 transition-colors"
            >
              <LogOut size={15} />
              Terminar jornada
            </button>
          </div>

        </div>

        {confirming && (
          <EndShiftConfirm
            activeCount={activeOrders.length}
            onConfirm={confirmEnd}
            onCancel={cancelConfirm}
          />
        )}
      </div>
    )
  }

  return (
    /* Container fills the main element exactly */
    <div className="relative w-full h-full">

      {/* MAP — true full screen, behind all overlays */}
      <MockMap
        activeOrders={activeOrders}
        controllerRef={controllerRef}
        onAdvance={handleControllerAdvance}
        onMetricsUpdate={(m) => setLiveDistanceM(m.restanteM)}
        className="absolute inset-0 w-full h-full rounded-none"
        showFullRoute
        followDriver
      />

      {/* LEYENDA — debajo del banner, esquina izquierda */}
      {activeOrders.length > 0 && (
        <div
          className="absolute left-3 z-20 pointer-events-none"
          style={{ top: `calc(max(env(safe-area-inset-top, 0px), 12px) + 76px)` }}
        >
          <div className="bg-white/90 backdrop-blur-sm rounded-xl px-2.5 py-2 border border-vygo-border flex flex-col gap-1.5 shadow-card">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-white border-2 border-vygo-green flex-shrink-0" />
              <span className="text-[11px] text-vygo-white">Recoger #1</span>
            </div>
            <div className="flex items-center gap-2">
              <svg width="14" height="13" viewBox="0 0 36 34" className="flex-shrink-0">
                <polygon points="18,2 1,33 35,33" fill="white" stroke="#6FA800" strokeWidth="3" strokeLinejoin="round"/>
              </svg>
              <span className="text-[11px] text-vygo-white">Recoger extra</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-3 rounded-full bg-vygo-warning flex-shrink-0" />
              <span className="text-[11px] text-vygo-white">Entregar</span>
            </div>
          </div>
        </div>
      )}

      {/* TOP TURN BANNER — estilo Waze / Google Maps */}
      <div
        className="absolute left-3 right-3 z-20"
        style={{ top: `max(env(safe-area-inset-top, 0px), 12px)` }}
      >
        <div className="bg-vygo-card/95 backdrop-blur-xl rounded-2xl border border-vygo-border px-3.5 py-3 shadow-card flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className="w-9 h-9 flex items-center justify-center rounded-xl bg-vygo-card-2 border border-vygo-border text-vygo-secondary flex-shrink-0"
            >
              <ArrowLeft size={16} />
            </button>

            {/* Icono de maniobra con indicador de tipo de parada */}
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-vygo-green/15 border border-vygo-green/30 text-vygo-green flex-shrink-0 shadow-sm">
              {currentStop?.type === 'pickup' ? <Store size={20} /> : <MapPin size={20} />}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-1.5">
                <span className="text-base font-black text-vygo-green tracking-tight">
                  En {distLabel}
                </span>
                <span className="text-[11px] text-vygo-secondary">
                  · ~{minutesToStop} min
                </span>
              </div>
              <p className="text-xs font-semibold text-vygo-white truncate">
                {currentStop?.type === 'pickup'
                  ? `Recoger: ${primaryOrder?.pickup.address.split(',')[0]}`
                  : `Entregar: ${primaryOrder?.dropoff.address.split(',')[0]}`}
              </p>
            </div>

            {/* Badge de ETA */}
            <div className="flex flex-col items-end flex-shrink-0">
              <div className="flex items-center gap-1 bg-vygo-green/10 px-2 py-0.5 rounded-full border border-vygo-green/20">
                <span className="w-1.5 h-1.5 rounded-full bg-vygo-green animate-pulse" />
                <span className="text-[10px] text-vygo-green font-medium">En ruta</span>
              </div>
              <span className="text-[11px] font-bold text-vygo-white mt-1 tabular-nums">
                {etaTimeStr}
              </span>
            </div>
          </div>

          {/* Siguiente parada preview si existe */}
          {nextStop && (
            <div className="pt-2 border-t border-vygo-border/50 flex items-center gap-1.5 text-[11px] text-vygo-secondary">
              <span className="text-[10px] uppercase font-bold text-vygo-green">Luego:</span>
              <span className="truncate text-vygo-white">
                {nextStop.type === 'pickup'
                  ? `Recoger orden #${nextOrder?.orderNumber ?? '2'} (${nextOrder?.pickup.address.split(',')[0]})`
                  : `Entregar orden #${nextOrder?.orderNumber ?? '1'} (${nextOrder?.dropoff.address.split(',')[0]})`}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* BOTTOM NAVIGATION HUD — mide la ruta completa y el progreso estilo Waze */}
      <div
        className="absolute left-3 right-3 z-20"
        style={{ bottom: `max(env(safe-area-inset-bottom, 0px), 12px)` }}
      >
        <div className="bg-vygo-card/95 backdrop-blur-xl rounded-2xl border border-vygo-border shadow-sheet overflow-hidden">
          {/* Barra de progreso visual que mide el avance en la ruta de A* */}
          <div className="h-1.5 bg-vygo-card-2 relative overflow-hidden">
            <div
              className="h-full bg-vygo-green transition-all duration-500 rounded-full"
              style={{ width: `${Math.max(5, progressPct)}%` }}
            />
          </div>

          <div className="px-3.5 py-3 flex flex-col gap-2.5">
            {/* Tira métrica de la ruta: restante km, tiempo restante y parada actual */}
            <div className="flex items-center justify-between text-xs py-0.5 border-b border-vygo-border/50">
              <div className="flex items-center gap-1.5">
                <Navigation size={13} className="text-vygo-green" />
                <span className="font-bold text-vygo-white">{formatDistance(totalRemainingKm)}</span>
                <span className="text-vygo-secondary">restantes</span>
              </div>

              <span className="text-vygo-secondary">
                Parada <b className="text-vygo-white">{currentStopIndex + 1}</b> de {totalStops || activeOrders.length * 2}
              </span>

              {primaryOrder && (
                <span className="font-bold text-vygo-green text-money">
                  {formatCurrency(primaryOrder.earnings)}
                </span>
              )}
            </div>

            {/* Accesos rápidos de navegación externa si el repartidor lo desea */}
            {targetCoords && (
              <div className="flex items-center gap-2">
                <a
                  href={`https://waze.com/ul?ll=${targetCoords.lat},${targetCoords.lng}&navigate=yes`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex-1 flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg bg-vygo-card-2 border border-vygo-border text-[11px] font-semibold text-vygo-white hover:bg-vygo-border/40 transition-colors"
                >
                  <Navigation size={12} className="text-vygo-green" />
                  Abrir Waze
                </a>
                <a
                  href={`https://www.google.com/maps/dir/?api=1&destination=${targetCoords.lat},${targetCoords.lng}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex-1 flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg bg-vygo-card-2 border border-vygo-border text-[11px] font-semibold text-vygo-white hover:bg-vygo-border/40 transition-colors"
                >
                  <ExternalLink size={12} className="text-vygo-green" />
                  Google Maps
                </a>
              </div>
            )}

            {/* Botón principal de avance de entrega */}
            <Button
              onClick={handleAdvance}
              size="lg"
              className="w-full h-12 text-sm font-bold shadow-md"
              disabled={primaryOrder?.status === 'delivered'}
            >
              {actionLabel}
            </Button>

            {/* Próximo pedido compacto */}
            {nextOrder && (
              <div className="flex items-center gap-1.5 pt-1">
                <span className="text-[10px] text-vygo-secondary uppercase tracking-wide">Siguiente</span>
                <PlatformBadge platform={nextOrder.platform} size="sm" showDot />
                <span className="text-[11px] font-semibold text-vygo-white ml-auto">
                  {formatCurrency(nextOrder.earnings)}
                </span>
                <span className="text-[10px] text-vygo-secondary">
                  {formatDistance(nextOrder.distanceKm)} · {formatMinutes(nextOrder.estimatedMinutes)}
                </span>
              </div>
            )}

            {/* Terminar jornada */}
            <button
              onClick={() => tryEndShift(() => navigate('/'))}
              className="flex items-center justify-center gap-1.5 w-full py-1.5 rounded-xl border border-vygo-danger/25 bg-vygo-danger/5 text-vygo-danger text-xs font-medium hover:bg-vygo-danger/10 transition-colors"
            >
              <LogOut size={12} />
              Terminar jornada
            </button>
          </div>
        </div>
      </div>

      {confirming && (
        <EndShiftConfirm
          activeCount={activeOrders.length}
          onConfirm={() => { confirmEnd(); navigate('/') }}
          onCancel={cancelConfirm}
        />
      )}
    </div>
  )
}
