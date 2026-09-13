import { ChevronRight, StopCircle, Zap, Clock, TrendingUp, Navigation2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useDriverStore } from '@/stores/driver.store'
import { useOrdersStore } from '@/stores/orders.store'
import { useEndShift } from '@/hooks/useEndShift'
import { useCountUp } from '@/hooks/useCountUp'
import { usePlatformConnections } from '@/hooks/usePlatformConnections'
import { useRouteStore } from '@/stores/route.store'
import { EndShiftConfirm } from '@/components/EndShiftConfirm'
import { DriverStatusBadge } from '@/components/DriverStatusBadge'
import { MockMap } from '@/components/maps/MockMap'
import { PlatformBadge } from '@/components/PlatformBadge'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDistance, formatMinutes } from '@/lib/utils'

export function HomePage() {
  const driver = useDriverStore((s) => s.driver)
  const driverStatus = useDriverStore((s) => s.status)
  const { connections: platformConnections } = usePlatformConnections()
  const routeGeoJSON = useRouteStore((s) => s.routeGeoJSON)
  const todayEarnings = useDriverStore((s) => s.todayEarnings)
  const earningsPerHour = useDriverStore((s) => s.earningsPerHour)
  const completedOrders = useDriverStore((s) => s.completedOrders)
  const startShift = useDriverStore((s) => s.startShift)
  const activeOrders = useOrdersStore((s) => s.activeOrders)
  const { tryEndShift, confirming, confirmEnd, cancelConfirm } = useEndShift()

  const animatedEarnings = useCountUp(todayEarnings)
  const animatedOrders = useCountUp(completedOrders)

  const isOnline = driverStatus !== 'offline'
  const nextOrder = activeOrders[0] ?? null
  const hasActivity = todayEarnings > 0 || completedOrders > 0

  return (
    <div className="flex flex-col h-full">

      {/* ── OFFLINE ────────────────────────────────────────── */}
      {!isOnline && (
        <div className="flex flex-col h-full overflow-y-auto scrollbar-none">

          {/* Header */}
          <div
            className="flex items-center justify-between px-4 pb-3"
            style={{ paddingTop: `max(env(safe-area-inset-top, 0px), 16px)` }}
          >
            <div className="flex flex-col gap-1">
              <h1 className="text-2xl font-bold text-vygo-white tracking-tight">
                Hola, {driver.name} 👋
              </h1>
              <DriverStatusBadge status={driverStatus} />
            </div>
          </div>

          <div className="flex flex-col gap-4 px-4 pb-6 flex-1">

            {/* Hero card — VYGO value prop */}
            <div className="relative overflow-hidden rounded-3xl bg-vygo-green p-5">
              <div className="absolute -top-8 -right-8 w-40 h-40 rounded-full bg-white/10" />
              <div className="absolute -bottom-6 -left-4 w-28 h-28 rounded-full bg-white/8" />
              <div className="relative">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-xl bg-white/20 flex items-center justify-center">
                    <Zap size={16} className="text-white" />
                  </div>
                  <span className="text-white font-bold text-sm">Copiloto activo</span>
                </div>
                <p className="text-white font-black text-2xl leading-tight mb-1">
                  Gana más.<br />Maneja menos.
                </p>
                <p className="text-white/75 text-xs leading-relaxed">
                  VYGO evalúa cada oferta y solo te muestra<br />
                  las que mejoran tu tasa $/hora.
                </p>
                <div className="flex items-center gap-3 mt-4">
                  <div className="bg-white/20 rounded-xl px-3 py-1.5 text-center">
                    <p className="text-white font-black text-base leading-none">+66%</p>
                    <p className="text-white/70 text-[10px] mt-0.5">vs sin VYGO</p>
                  </div>
                  <div className="bg-white/20 rounded-xl px-3 py-1.5 text-center">
                    <p className="text-white font-black text-base leading-none">$169/h</p>
                    <p className="text-white/70 text-[10px] mt-0.5">promedio</p>
                  </div>
                  <div className="bg-white/20 rounded-xl px-3 py-1.5 text-center">
                    <p className="text-white font-black text-base leading-none">&lt;1ms</p>
                    <p className="text-white/70 text-[10px] mt-0.5">decisión</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Plataformas */}
            <div>
              <p className="text-xs text-vygo-secondary uppercase tracking-widest mb-2.5">Plataformas conectadas</p>
              {platformConnections.length > 0 ? (
                <div className="flex gap-2 flex-wrap">
                  {platformConnections.map((c) => (
                    <PlatformBadge key={c.platform} platform={c.platform} size="md" />
                  ))}
                </div>
              ) : (
                <Link to="/profile" className="flex items-center gap-2 text-xs text-vygo-green font-medium">
                  <span className="w-6 h-6 rounded-lg bg-vygo-green/10 flex items-center justify-center">+</span>
                  Conectar plataformas en perfil
                </Link>
              )}
            </div>

            {/* Stats — solo si hay actividad */}
            {hasActivity && (
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3 text-center">
                  <p className="text-base font-bold text-vygo-green text-money">{formatCurrency(animatedEarnings)}</p>
                  <p className="text-[11px] text-vygo-secondary mt-0.5">Ganado hoy</p>
                </div>
                <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3 text-center">
                  <p className="text-base font-bold text-vygo-white">{animatedOrders}</p>
                  <p className="text-[11px] text-vygo-secondary mt-0.5">Entregas</p>
                </div>
                <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3 text-center">
                  <p className="text-base font-bold text-vygo-white text-money">${earningsPerHour}/h</p>
                  <p className="text-[11px] text-vygo-secondary mt-0.5">Promedio</p>
                </div>
              </div>
            )}

            {/* CTA */}
            <Button onClick={startShift} size="xl" className="w-full h-14 text-base font-semibold">
              Comenzar jornada
            </Button>

            {/* Insight cards */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3.5">
                <div className="flex items-center gap-1.5 mb-2">
                  <Clock size={13} className="text-vygo-secondary" />
                  <p className="text-[11px] text-vygo-secondary font-semibold uppercase tracking-wide">Mejor horario</p>
                </div>
                <p className="text-sm font-bold text-vygo-white">7PM – 10PM</p>
                <p className="text-[11px] text-vygo-secondary mt-0.5">Zona Centro · Tec</p>
              </div>
              <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3.5">
                <div className="flex items-center gap-1.5 mb-2">
                  <TrendingUp size={13} className="text-vygo-secondary" />
                  <p className="text-[11px] text-vygo-secondary font-semibold uppercase tracking-wide">Meta sugerida</p>
                </div>
                <p className="text-sm font-bold text-vygo-white">$800</p>
                <p className="text-[11px] text-vygo-secondary mt-0.5">en 5h · $160/h</p>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ── ONLINE ─────────────────────────────────────────── */}
      {isOnline && (
        <div className="flex flex-col h-full">

          {/* Header flotante sobre el mapa */}
          <div
            className="px-4 pb-2 z-10 relative"
            style={{ paddingTop: `max(env(safe-area-inset-top, 0px), 16px)` }}
          >
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-0.5">
                <h1 className="text-xl font-bold text-vygo-white tracking-tight leading-none">
                  Hola, {driver.name}
                </h1>
                <DriverStatusBadge status={driverStatus} />
              </div>
            </div>
          </div>

          {/* Mapa — crece para llenar el espacio disponible */}
          <div className="relative flex-1 min-h-0">
            <MockMap
              activeOrders={activeOrders}
              routeGeoJSON={routeGeoJSON}
              className="absolute inset-0 w-full h-full rounded-none"
              showFullRoute
            />
          </div>

          {/* Bottom card — compacto */}
          <div className="px-3 pb-3 pt-0 shrink-0">
            <div className="bg-white/90 backdrop-blur-xl border border-vygo-border rounded-2xl shadow-sheet overflow-hidden">

              {/* HUD strip */}
              <div className="flex items-center px-4 py-2.5 border-b border-vygo-border/50">
                <div className="flex-1 text-center">
                  <span className="text-lg font-bold text-vygo-green text-money">{formatCurrency(animatedEarnings)}</span>
                  <span className="text-[10px] text-vygo-secondary ml-1">hoy</span>
                </div>
                <div className="w-px h-6 bg-vygo-border" />
                <div className="flex-1 text-center">
                  <span className="text-lg font-bold text-vygo-white">{animatedOrders}</span>
                  <span className="text-[10px] text-vygo-secondary ml-1">pedidos</span>
                </div>
                <div className="w-px h-6 bg-vygo-border" />
                <div className="flex-1 text-center">
                  <span className="text-lg font-bold text-vygo-white text-money">${earningsPerHour}/h</span>
                  <span className="text-[10px] text-vygo-secondary ml-1">ρ</span>
                </div>
              </div>

              {/* Content */}
              <div className="px-4 py-3">
                {nextOrder ? (
                  <div className="flex flex-col gap-2.5">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-vygo-secondary uppercase tracking-widest">Siguiente entrega</p>
                      {activeOrders.length > 1 && (
                        <Link to="/orders" className="text-xs text-vygo-green font-semibold flex items-center gap-0.5">
                          +{activeOrders.length - 1} más <ChevronRight size={12} />
                        </Link>
                      )}
                    </div>
                    <Link to="/route" className="block bg-vygo-card border border-vygo-border rounded-2xl p-3 active:scale-[0.99] transition-transform">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <PlatformBadge platform={nextOrder.platform} size="sm" />
                          <span className="text-xs text-vygo-secondary">#{nextOrder.orderNumber}</span>
                        </div>
                        <span className="text-xl font-bold text-vygo-green text-money leading-none">{formatCurrency(nextOrder.earnings)}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Navigation2 size={11} className="text-vygo-secondary flex-shrink-0" />
                        <p className="text-sm font-semibold text-vygo-white truncate">{nextOrder.pickup.address}</p>
                      </div>
                      <div className="flex items-center justify-between mt-1.5">
                        <div className="flex items-center gap-2 text-xs text-vygo-secondary">
                          <span>{formatDistance(nextOrder.distanceKm)}</span>
                          <span>·</span>
                          <span>{formatMinutes(nextOrder.estimatedMinutes)}</span>
                        </div>
                        <span className="text-xs text-vygo-green font-semibold flex items-center gap-0.5">
                          Ver ruta <ChevronRight size={12} />
                        </span>
                      </div>
                    </Link>
                  </div>
                ) : (
                  /* Radar */
                  <div className="flex items-center gap-4 py-1">
                    <div className="relative w-12 h-12 flex-shrink-0 flex items-center justify-center">
                      <span className="absolute inset-0 rounded-full border border-vygo-green/25 animate-ping" style={{ animationDuration: '2s' }} />
                      <span className="absolute inset-1.5 rounded-full border border-vygo-green/30 animate-ping" style={{ animationDuration: '2s', animationDelay: '0.5s' }} />
                      <div className="absolute inset-3 rounded-full bg-vygo-green/15 border border-vygo-green/40 flex items-center justify-center">
                        <Zap size={12} className="text-vygo-green" />
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-vygo-white leading-tight">Buscando el mejor pedido</p>
                      <p className="text-xs text-vygo-secondary mt-0.5">Solo te muestro los que mejoran tu $/h</p>
                    </div>
                  </div>
                )}

                <button
                  onClick={() => tryEndShift()}
                  className="flex items-center justify-center gap-1.5 w-full mt-2.5 py-1.5 rounded-xl text-vygo-secondary/50 text-xs hover:text-vygo-danger transition-colors"
                >
                  <StopCircle size={12} />
                  Terminar jornada
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
