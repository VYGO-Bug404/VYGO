import { ChevronRight, StopCircle, TrendingUp, Zap, MapPin } from 'lucide-react'
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

  return (
    <div className="flex flex-col min-h-full">

      {/* ── Header ── */}
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

      {isOnline ? (
        <>
          {/* ── ONLINE: Mapa grande + HUD ── */}
          <div className="relative">
            <MockMap
              activeOrders={activeOrders}
              routeGeoJSON={routeGeoJSON}
              className="h-[360px] w-full rounded-none"
              showFullRoute
            />
            <div className="absolute bottom-0 left-0 right-0 px-3 pb-3">
              <div className="bg-white/85 backdrop-blur-xl border border-vygo-border rounded-2xl px-4 py-3 flex items-center">
                <div className="flex-1 flex flex-col items-center">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xl font-bold text-vygo-green text-money">
                      {formatCurrency(animatedEarnings)}
                    </span>
                    <span className="flex items-center gap-0.5 text-[10px] font-semibold text-vygo-green bg-vygo-green/10 px-1.5 py-0.5 rounded-full">
                      <TrendingUp size={9} />12%
                    </span>
                  </div>
                  <span className="text-[11px] text-vygo-secondary mt-0.5">Hoy</span>
                </div>
                <div className="w-px h-8 bg-vygo-border mx-1" />
                <div className="flex-1 flex flex-col items-center">
                  <span className="text-xl font-bold text-vygo-white">{animatedOrders}</span>
                  <span className="text-[11px] text-vygo-secondary mt-0.5">Pedidos</span>
                </div>
                <div className="w-px h-8 bg-vygo-border mx-1" />
                <div className="flex-1 flex flex-col items-center">
                  <span className="text-xl font-bold text-vygo-white text-money">${earningsPerHour}/h</span>
                  <span className="text-[11px] text-vygo-secondary mt-0.5">Rendimiento</span>
                </div>
              </div>
            </div>
          </div>

          {/* ── Content online ── */}
          <div className="flex-1 flex flex-col px-4 pt-4 pb-2 gap-3">
            {nextOrder ? (
              /* Siguiente entrega */
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-vygo-secondary uppercase tracking-widest">Siguiente entrega</p>
                  {activeOrders.length > 1 && (
                    <Link to="/orders" className="text-xs text-vygo-green font-semibold flex items-center gap-0.5">
                      +{activeOrders.length - 1} más <ChevronRight size={12} />
                    </Link>
                  )}
                </div>
                <Link to="/route" className="block bg-vygo-card border border-vygo-border rounded-2xl p-4 hover:border-vygo-green/30 transition-colors active:scale-[0.99]">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <PlatformBadge platform={nextOrder.platform} size="md" />
                      <span className="text-xs text-vygo-secondary">#{nextOrder.orderNumber}</span>
                    </div>
                    <span className="text-2xl font-bold text-vygo-green text-money leading-none">{formatCurrency(nextOrder.earnings)}</span>
                  </div>
                  <p className="text-[15px] font-semibold text-vygo-white mb-3 leading-tight">{nextOrder.pickup.address}</p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 text-sm text-vygo-secondary">
                      <span>{formatDistance(nextOrder.distanceKm)}</span>
                      <span>·</span>
                      <span>{formatMinutes(nextOrder.estimatedMinutes)}</span>
                    </div>
                    <div className="flex items-center gap-1 text-vygo-green text-sm font-semibold">
                      Ver ruta <ChevronRight size={14} />
                    </div>
                  </div>
                </Link>
                {activeOrders.length > 1 && (
                  <div className="flex items-center gap-1.5 px-1">
                    {activeOrders.slice(1).map((o, i) => (
                      <div key={o.id} className="flex items-center gap-1">
                        <PlatformBadge platform={o.platform} size="sm" />
                        <span className="text-xs text-vygo-secondary font-medium text-money">{formatCurrency(o.earnings)}</span>
                        {i < activeOrders.length - 2 && <span className="text-vygo-border ml-0.5">·</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* Radar — esperando pedido */
              <div className="flex-1 flex flex-col items-center justify-center gap-4 py-6">
                <div className="relative w-20 h-20 flex items-center justify-center">
                  <span className="absolute inset-0 rounded-full border border-vygo-green/20 animate-ping" style={{ animationDuration: '2s' }} />
                  <span className="absolute inset-2 rounded-full border border-vygo-green/25 animate-ping" style={{ animationDuration: '2s', animationDelay: '0.4s' }} />
                  <span className="absolute inset-4 rounded-full border border-vygo-green/35 animate-ping" style={{ animationDuration: '2s', animationDelay: '0.8s' }} />
                  <div className="absolute inset-6 rounded-full bg-vygo-green/10 border border-vygo-green/30 flex items-center justify-center">
                    <Zap size={16} className="text-vygo-green" />
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-base font-semibold text-vygo-white mb-1">Buscando el mejor pedido</p>
                  <p className="text-xs text-vygo-secondary max-w-[200px] leading-relaxed">
                    VYGO solo te muestra pedidos que mejoran tus ganancias.
                  </p>
                </div>
              </div>
            )}

            <button
              onClick={() => tryEndShift()}
              className="flex items-center justify-center gap-2 w-full h-10 rounded-2xl text-vygo-secondary/60 text-sm hover:text-vygo-danger transition-colors"
            >
              <StopCircle size={14} />
              Terminar jornada
            </button>
          </div>
        </>
      ) : (
        <>
          {/* ── OFFLINE: layout sin hueco ── */}

          {/* Mapa compacto */}
          <div className="relative mx-4 rounded-2xl overflow-hidden border border-vygo-border">
            <MockMap
              activeOrders={[]}
              className="h-[180px] w-full"
            />
            <div className="absolute inset-0 flex items-center justify-center bg-white/50 backdrop-blur-[1px]">
              <div className="flex items-center gap-2 bg-vygo-card/90 border border-vygo-border rounded-full px-3 py-1.5">
                <MapPin size={12} className="text-vygo-green" />
                <span className="text-xs text-vygo-secondary font-medium">Tu zona · Monterrey</span>
              </div>
            </div>
          </div>

          {/* Plataformas conectadas */}
          <div className="px-4 pt-4">
            <p className="text-xs text-vygo-secondary uppercase tracking-widest mb-2">Plataformas conectadas</p>
            {platformConnections.length > 0 ? (
              <div className="flex gap-2">
                {platformConnections.map((c) => (
                  <PlatformBadge key={c.platform} platform={c.platform} size="md" />
                ))}
              </div>
            ) : (
              <p className="text-xs text-vygo-secondary/50">
                Sin plataformas — agrégalas en tu perfil
              </p>
            )}
          </div>

          {/* Stats de referencia */}
          <div className="px-4 pt-3">
            <div className="bg-vygo-card border border-vygo-border rounded-2xl px-4 py-3 flex items-center gap-4">
              <div className="flex-1 text-center">
                <p className="text-lg font-bold text-vygo-white text-money">{formatCurrency(todayEarnings)}</p>
                <p className="text-[11px] text-vygo-secondary mt-0.5">Ganado hoy</p>
              </div>
              <div className="w-px h-8 bg-vygo-border" />
              <div className="flex-1 text-center">
                <p className="text-lg font-bold text-vygo-white">{completedOrders}</p>
                <p className="text-[11px] text-vygo-secondary mt-0.5">Entregas</p>
              </div>
              <div className="w-px h-8 bg-vygo-border" />
              <div className="flex-1 text-center">
                <p className="text-lg font-bold text-vygo-green text-money">${earningsPerHour}/h</p>
                <p className="text-[11px] text-vygo-secondary mt-0.5">Promedio</p>
              </div>
            </div>
          </div>

          {/* CTA */}
          <div className="px-4 pt-4 pb-2 flex flex-col gap-2">
            <Button onClick={startShift} size="xl" className="w-full h-14 text-base font-semibold">
              Comenzar jornada
            </Button>
            <p className="text-center text-xs text-vygo-secondary/60">
              VYGO analiza cada pedido y solo te muestra los que convienen
            </p>
          </div>
        </>
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
