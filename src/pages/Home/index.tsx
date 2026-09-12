import { Bell, ChevronRight, StopCircle, TrendingUp, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useDriverStore } from '@/stores/driver.store'
import { useOrdersStore } from '@/stores/orders.store'
import { DriverStatusBadge } from '@/components/DriverStatusBadge'
import { MockMap } from '@/components/maps/MockMap'
import { PlatformBadge } from '@/components/PlatformBadge'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDistance, formatMinutes } from '@/lib/utils'

export function HomePage() {
  const driver = useDriverStore((s) => s.driver)
  const driverStatus = useDriverStore((s) => s.status)
  const todayEarnings = useDriverStore((s) => s.todayEarnings)
  const earningsPerHour = useDriverStore((s) => s.earningsPerHour)
  const completedOrders = useDriverStore((s) => s.completedOrders)
  const startShift = useDriverStore((s) => s.startShift)
  const endShift = useDriverStore((s) => s.endShift)
  const activeOrders = useOrdersStore((s) => s.activeOrders)

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

        <button className="relative w-10 h-10 flex items-center justify-center rounded-xl bg-vygo-card border border-vygo-border text-vygo-secondary hover:text-vygo-white transition-colors">
          <Bell size={18} />
          {isOnline && (
            <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-vygo-green" />
          )}
        </button>
      </div>

      {/* ── Map + metrics overlay ── */}
      <div className="relative">
        <MockMap
          activeOrders={activeOrders}
          className="h-[360px] w-full rounded-none"
          showFullRoute={isOnline}
        />

        {/* Metrics HUD — floats at bottom of map */}
        <div className="absolute bottom-0 left-0 right-0 px-3 pb-3">
          <div className="bg-vygo-bg/85 backdrop-blur-xl border border-vygo-border rounded-2xl px-4 py-3 flex items-center">
            {/* Earnings */}
            <div className="flex-1 flex flex-col items-center">
              <div className="flex items-center gap-1.5">
                <span className="text-xl font-bold text-vygo-green text-money">
                  {formatCurrency(todayEarnings)}
                </span>
                <span className="flex items-center gap-0.5 text-[10px] font-semibold text-vygo-green bg-vygo-green/10 px-1.5 py-0.5 rounded-full">
                  <TrendingUp size={9} />
                  12%
                </span>
              </div>
              <span className="text-[11px] text-vygo-secondary mt-0.5">Hoy</span>
            </div>

            <div className="w-px h-8 bg-vygo-border mx-1" />

            {/* Orders */}
            <div className="flex-1 flex flex-col items-center">
              <span className="text-xl font-bold text-vygo-white">{completedOrders}</span>
              <span className="text-[11px] text-vygo-secondary mt-0.5">Pedidos</span>
            </div>

            <div className="w-px h-8 bg-vygo-border mx-1" />

            {/* Per hour */}
            <div className="flex-1 flex flex-col items-center">
              <span className="text-xl font-bold text-vygo-white text-money">${earningsPerHour}/h</span>
              <span className="text-[11px] text-vygo-secondary mt-0.5">Rendimiento</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 flex flex-col px-4 pt-4 pb-2 gap-3">

        {!isOnline ? (
          /* ── Offline CTA ── */
          <div className="flex-1 flex flex-col justify-center gap-4 py-4">
            <div className="flex flex-col gap-1">
              <p className="text-lg font-semibold text-vygo-white">
                Listo para comenzar
              </p>
              <p className="text-sm text-vygo-secondary leading-relaxed">
                Activa tu jornada y VYGO analiza cada pedido automáticamente.
              </p>
            </div>
            <Button onClick={startShift} size="xl" className="w-full h-14 text-base font-semibold">
              Comenzar jornada
            </Button>
          </div>

        ) : nextOrder ? (
          /* ── Siguiente entrega ── */
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-vygo-secondary uppercase tracking-widest">
                Siguiente entrega
              </p>
              {activeOrders.length > 1 && (
                <Link to="/orders" className="text-xs text-vygo-green font-semibold flex items-center gap-0.5">
                  +{activeOrders.length - 1} más
                  <ChevronRight size={12} />
                </Link>
              )}
            </div>

            {/* Order card */}
            <Link to="/route" className="block bg-vygo-card border border-vygo-border rounded-2xl p-4 hover:border-vygo-green/30 transition-colors active:scale-[0.99]">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <PlatformBadge platform={nextOrder.platform} size="md" />
                  <span className="text-xs text-vygo-secondary">#{nextOrder.orderNumber}</span>
                </div>
                <span className="text-2xl font-bold text-vygo-green text-money leading-none">
                  {formatCurrency(nextOrder.earnings)}
                </span>
              </div>

              <p className="text-[15px] font-semibold text-vygo-white mb-3 leading-tight">
                {nextOrder.pickup.address}
              </p>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-sm text-vygo-secondary">
                  <span>{formatDistance(nextOrder.distanceKm)}</span>
                  <span>·</span>
                  <span>{formatMinutes(nextOrder.estimatedMinutes)}</span>
                </div>
                <div className="flex items-center gap-1 text-vygo-green text-sm font-semibold">
                  Ver ruta
                  <ChevronRight size={14} />
                </div>
              </div>
            </Link>

            {/* Other platforms in route */}
            {activeOrders.length > 1 && (
              <div className="flex items-center gap-2 px-1">
                <div className="flex items-center gap-1.5">
                  {activeOrders.slice(1).map((o, i) => (
                    <div key={o.id} className="flex items-center gap-1">
                      <PlatformBadge platform={o.platform} size="sm" />
                      <span className="text-xs text-vygo-secondary font-medium text-money">
                        {formatCurrency(o.earnings)}
                      </span>
                      {i < activeOrders.length - 2 && (
                        <span className="text-vygo-border ml-0.5">·</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

        ) : (
          /* ── Online, waiting ── */
          <div className="flex-1 flex flex-col items-center justify-center gap-3 py-6">
            <div className="w-10 h-10 rounded-full border border-vygo-green/30 flex items-center justify-center">
              <Zap size={18} className="text-vygo-green" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-vygo-white mb-1">Buscando el mejor pedido</p>
              <p className="text-xs text-vygo-secondary max-w-[200px] leading-relaxed">
                VYGO solo te muestra pedidos que mejoran tus ganancias.
              </p>
            </div>
          </div>
        )}

        {/* ── Terminar jornada ── */}
        {isOnline && (
          <button
            onClick={endShift}
            className="flex items-center justify-center gap-2 w-full h-10 rounded-2xl text-vygo-secondary/60 text-sm hover:text-vygo-danger transition-colors"
          >
            <StopCircle size={14} />
            Terminar jornada
          </button>
        )}
      </div>
    </div>
  )
}
