import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ChevronRight, LogOut } from 'lucide-react'
import { useOrdersStore } from '@/stores/orders.store'
import { useRouteStore } from '@/stores/route.store'
import { useDriverStore } from '@/stores/driver.store'
import { useActiveRoute } from '@/hooks/useActiveRoute'
import { MockMap } from '@/components/maps/MockMap'
import { PlatformBadge } from '@/components/PlatformBadge'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDistance, formatMinutes } from '@/lib/utils'

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
  const { currentStop, nextStop, totalStops } = useActiveRoute()
  const currentStopIndex = useRouteStore((s) => s.currentStopIndex)

  const endShift = useDriverStore((s) => s.endShift)
  const primaryOrder = currentStop?.order ?? activeOrders[0] ?? null
  const nextOrder = nextStop?.order ?? activeOrders[1] ?? null

  const progressPct = totalStops > 0 ? (currentStopIndex / totalStops) * 100 : 0

  const handleAdvance = () => {
    if (primaryOrder) {
      advanceOrder(primaryOrder.id)
      advanceStop()
    }
  }

  const actionLabel = primaryOrder
    ? (STATUS_LABEL[primaryOrder.status] ?? 'Pedido entregado')
    : 'Completado'

  const destination = currentStop
    ? currentStop.type === 'pickup'
      ? primaryOrder?.pickup.address
      : primaryOrder?.dropoff.address
    : null

  if (!primaryOrder && activeOrders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 px-4">
        <p className="text-vygo-secondary text-center">No tienes pedidos activos.</p>
        <Button variant="ghost" onClick={() => navigate('/')}>Volver al inicio</Button>
      </div>
    )
  }

  return (
    /* Container fills the main element exactly */
    <div className="relative w-full h-full">

      {/* MAP — true full screen, behind all overlays */}
      <MockMap
        activeOrders={activeOrders}
        className="absolute inset-0 w-full h-full rounded-none"
        showFullRoute
      />

      {/* TOP BANNER — floats over map */}
      <div
        className="absolute left-3 right-3 z-20"
        style={{ top: `max(env(safe-area-inset-top, 0px), 12px)` }}
      >
        <div className="flex items-center gap-2 bg-vygo-card/90 backdrop-blur-xl rounded-2xl border border-vygo-border px-3 py-2.5 shadow-card">
          <button
            onClick={() => navigate(-1)}
            className="w-8 h-8 flex items-center justify-center rounded-xl bg-vygo-card-2 border border-vygo-border text-vygo-secondary flex-shrink-0"
          >
            <ArrowLeft size={16} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1">
              <ChevronRight size={13} className="text-vygo-green flex-shrink-0" />
              <span className="text-sm font-bold text-vygo-white truncate">
                {currentStop?.type === 'pickup' ? 'Dirígete al restaurante' : 'Dirígete a entregar'}
              </span>
            </div>
            {destination && (
              <p className="text-xs text-vygo-secondary truncate pl-4">{destination}</p>
            )}
          </div>
          {/* En vivo badge */}
          <div className="flex items-center gap-1 flex-shrink-0">
            <span className="w-2 h-2 rounded-full bg-vygo-green animate-pulse" />
            <span className="text-[11px] text-vygo-green font-medium">En vivo</span>
          </div>
        </div>
      </div>

      {/* BOTTOM CARD — sits above safe area, no nav on this screen */}
      <div
        className="absolute left-3 right-3 z-20"
        style={{ bottom: `max(env(safe-area-inset-bottom, 0px), 12px)` }}
      >
        <div className="bg-vygo-card/92 backdrop-blur-xl rounded-2xl border border-vygo-border shadow-sheet overflow-hidden">
          {/* Progress bar */}
          <div className="h-[3px] bg-vygo-border">
            <div
              className="h-full bg-vygo-green transition-all duration-500 rounded-full"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          <div className="px-3 py-2.5 flex flex-col gap-2">
            {/* Order row: platform + # + entrega X/Y + earnings */}
            {primaryOrder && (
              <div className="flex items-center gap-2">
                <PlatformBadge platform={primaryOrder.platform} size="sm" />
                <span className="text-xs text-vygo-secondary">#{primaryOrder.orderNumber}</span>
                <span className="text-xs text-vygo-secondary ml-auto">
                  Entrega {currentStopIndex + 1}/{totalStops || activeOrders.length * 2}
                </span>
                <span className="text-sm font-bold text-vygo-green text-money">
                  {formatCurrency(primaryOrder.earnings)}
                </span>
              </div>
            )}

            {/* Main action button */}
            <Button
              onClick={handleAdvance}
              size="lg"
              className="w-full h-12"
              disabled={primaryOrder?.status === 'delivered'}
            >
              {actionLabel}
            </Button>

            {/* Next order — one compact line */}
            {nextOrder && (
              <div className="flex items-center gap-1.5">
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
              onClick={() => { endShift(); navigate('/') }}
              className="flex items-center justify-center gap-1.5 w-full py-2 rounded-xl border border-vygo-danger/25 bg-vygo-danger/5 text-vygo-danger text-xs font-medium hover:bg-vygo-danger/10 transition-colors"
            >
              <LogOut size={12} />
              Terminar jornada
            </button>
          </div>
        </div>
      </div>

    </div>
  )
}
