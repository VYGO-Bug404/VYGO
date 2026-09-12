import { MapPin, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Order } from '@/types/order'

interface OrderTimelineProps {
  order: Order
}

export function OrderTimeline({ order }: OrderTimelineProps) {
  const isPickedUp = ['picked_up', 'delivered'].includes(order.status)
  const isDelivered = order.status === 'delivered'

  return (
    <div className="space-y-0">
      <div className="flex gap-3">
        <div className="flex flex-col items-center">
          <div
            className={cn(
              'w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors',
              isPickedUp
                ? 'bg-vygo-green/15 border-vygo-green'
                : 'bg-vygo-card-2 border-vygo-warning'
            )}
          >
            {isPickedUp ? (
              <Check size={14} className="text-vygo-green" />
            ) : (
              <MapPin size={12} className="text-vygo-warning" />
            )}
          </div>
          <div className="w-0.5 h-12 bg-vygo-border mt-1" />
        </div>
        <div className="pt-1 pb-4">
          <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide mb-0.5">Recoger</p>
          <p className="text-sm font-semibold text-vygo-white">{order.pickup.name}</p>
          <p className="text-sm text-vygo-secondary">{order.pickup.address}</p>
          <p className="text-xs text-vygo-secondary">{order.pickup.neighborhood}</p>
        </div>
      </div>

      <div className="flex gap-3">
        <div className="flex flex-col items-center">
          <div
            className={cn(
              'w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors',
              isDelivered
                ? 'bg-vygo-green/15 border-vygo-green'
                : 'bg-vygo-card-2 border-vygo-green'
            )}
          >
            {isDelivered ? (
              <Check size={14} className="text-vygo-green" />
            ) : (
              <MapPin size={12} className="text-vygo-green" />
            )}
          </div>
        </div>
        <div className="pt-1">
          <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide mb-0.5">Entregar</p>
          <p className="text-sm font-semibold text-vygo-white">{order.dropoff.address}</p>
          <p className="text-xs text-vygo-secondary">{order.dropoff.neighborhood}</p>
        </div>
      </div>
    </div>
  )
}
