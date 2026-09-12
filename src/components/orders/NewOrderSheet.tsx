import { useState } from 'react'
import { X, MapPin, Clock, TrendingUp, Navigation } from 'lucide-react'
import { useOrdersStore } from '@/stores/orders.store'
import { PlatformBadge } from '@/components/PlatformBadge'
import { RecommendationBadge } from '@/components/RecommendationBadge'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDistance, formatMinutes } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { Order } from '@/types/order'

interface NewOrderSheetProps {
  order: Order
}

export function NewOrderSheet({ order }: NewOrderSheetProps) {
  const [accepting, setAccepting] = useState(false)
  const acceptOffer = useOrdersStore((s) => s.acceptOffer)
  const rejectOffer = useOrdersStore((s) => s.rejectOffer)

  const currentEph = order.currentEarningsPerHour ?? 192
  const projectedEph = order.projectedEarningsPerHour ?? currentEph
  const ephDiff = projectedEph - currentEph
  const isPositive = ephDiff > 0

  const handleAccept = async () => {
    setAccepting(true)
    await new Promise((r) => setTimeout(r, 300))
    acceptOffer(order)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center animate-fade-in">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={rejectOffer}
      />

      <div
        className="relative w-full max-w-[430px] bg-vygo-card rounded-t-3xl shadow-sheet animate-slide-up overflow-hidden"
        style={{ maxHeight: '92dvh' }}
      >
        <div className="overflow-y-auto scrollbar-none" style={{ maxHeight: '92dvh' }}>
          {/* Handle bar */}
          <div className="flex justify-center pt-3 pb-1">
            <div className="w-10 h-1 rounded-full bg-vygo-border" />
          </div>

          {/* Header */}
          <div className="flex items-start justify-between px-5 py-3">
            <div>
              <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide mb-1">
                Nuevo pedido
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <PlatformBadge platform={order.platform} size="lg" />
                {order.recommendation && (
                  <RecommendationBadge recommendation={order.recommendation} />
                )}
              </div>
            </div>
            <button
              onClick={rejectOffer}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-vygo-card-2 text-vygo-secondary hover:text-vygo-white transition-colors mt-1"
            >
              <X size={16} />
            </button>
          </div>

          {/* Earnings hero */}
          <div className="px-5 py-2">
            <div className="flex items-baseline gap-2">
              <span className="text-5xl font-bold text-vygo-green text-money">
                {formatCurrency(order.earnings)}
              </span>
              <span className="text-lg text-vygo-secondary font-medium">ganancia</span>
            </div>
          </div>

          {/* Pickup → Dropoff */}
          <div className="px-5 py-3">
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
                  <p className="text-sm font-semibold text-vygo-white">{order.pickup.name}</p>
                  <p className="text-xs text-vygo-secondary">{order.pickup.address} · {order.pickup.neighborhood}</p>
                </div>
              </div>

              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-vygo-green/15 border border-vygo-green/30 flex items-center justify-center flex-shrink-0">
                  <Navigation size={12} className="text-vygo-green" />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-vygo-secondary uppercase tracking-wide font-medium mb-0.5">Entregar</p>
                  <p className="text-sm font-semibold text-vygo-white">{order.dropoff.address}</p>
                  <p className="text-xs text-vygo-secondary">{order.dropoff.neighborhood}</p>
                </div>
              </div>
            </div>
          </div>

          {/* 4 metrics */}
          <div className="px-5 pb-2">
            <div className="grid grid-cols-4 gap-2">
              <MetricPill
                value={formatCurrency(order.earnings)}
                label="Ganancia"
                highlight
              />
              <MetricPill
                value={`+${formatMinutes(order.extraMinutes ?? order.estimatedMinutes)}`}
                label="Tiempo extra"
              />
              <MetricPill
                value={`+${formatDistance(order.extraDistanceKm ?? order.distanceKm)}`}
                label="Distancia"
              />
              <MetricPill
                value={`$${projectedEph}/h`}
                label="Nuevo $/h"
                highlight={isPositive}
              />
            </div>
          </div>

          {/* Earnings comparison card */}
          <div className="px-5 pb-3">
            <div
              className={cn(
                'rounded-2xl border p-4',
                isPositive
                  ? 'bg-vygo-green/5 border-vygo-green/20'
                  : 'bg-vygo-card-2 border-vygo-border'
              )}
            >
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={14} className={isPositive ? 'text-vygo-green' : 'text-vygo-secondary'} />
                <p className="text-sm font-semibold text-vygo-white">
                  {isPositive ? 'Encaja con tu ruta' : 'Impacto en tu ruta'}
                </p>
              </div>
              <p className="text-xs text-vygo-secondary mb-3 leading-relaxed">
                {isPositive
                  ? `Solo agrega ${formatMinutes(order.extraMinutes ?? order.estimatedMinutes)} a tu ruta actual y mejora tu ganancia por hora.`
                  : 'Este pedido no mejora significativamente tu ganancia por hora actual.'}
              </p>

              <div className="flex items-center gap-3">
                <div className="flex-1 text-center">
                  <p className="text-xs text-vygo-secondary mb-0.5">Actualmente</p>
                  <p className="text-lg font-bold text-vygo-secondary text-money">${currentEph}/h</p>
                </div>
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      'px-2 py-1 rounded-lg text-sm font-bold text-money',
                      isPositive ? 'bg-vygo-green/15 text-vygo-green' : 'bg-vygo-danger/15 text-vygo-danger'
                    )}
                  >
                    {isPositive ? '+' : ''}${Math.abs(ephDiff)}/h
                  </div>
                </div>
                <div className="flex-1 text-center">
                  <p className="text-xs text-vygo-secondary mb-0.5">Si aceptas</p>
                  <p
                    className={cn(
                      'text-lg font-bold text-money',
                      isPositive ? 'text-vygo-green' : 'text-vygo-white'
                    )}
                  >
                    ${projectedEph}/h
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="px-5 pb-6 grid grid-cols-2 gap-3">
            <Button
              variant="destructive"
              size="lg"
              onClick={rejectOffer}
              className="h-14"
            >
              Rechazar
            </Button>
            <Button
              variant="default"
              size="lg"
              onClick={handleAccept}
              disabled={accepting}
              className={cn(
                'h-14 transition-all duration-200',
                accepting && 'scale-95 opacity-80'
              )}
            >
              {accepting ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-vygo-bg/50 border-t-vygo-bg rounded-full animate-spin" />
                  Aceptando…
                </span>
              ) : (
                'Aceptar'
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricPill({ value, label, highlight = false }: { value: string; label: string; highlight?: boolean }) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl py-3 px-1 gap-0.5 border',
        highlight
          ? 'bg-vygo-green/8 border-vygo-green/20'
          : 'bg-vygo-card-2 border-vygo-border'
      )}
    >
      <span
        className={cn(
          'text-sm font-bold leading-tight text-money text-center',
          highlight ? 'text-vygo-green' : 'text-vygo-white'
        )}
      >
        {value}
      </span>
      <span className="text-[9px] text-vygo-secondary font-medium text-center leading-tight">
        {label}
      </span>
    </div>
  )
}
