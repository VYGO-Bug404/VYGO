import { MapPin, Clock, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { formatCurrency, formatDistance, formatMinutes } from '@/lib/utils'
import { PlatformBadge } from '@/components/PlatformBadge'
import type { Order } from '@/types/order'

interface OrderCardProps {
  order: Order
  stopNumber?: number
  className?: string
  compact?: boolean
}

export function OrderCard({ order, stopNumber, className, compact = false }: OrderCardProps) {
  return (
    <Link
      to={`/orders/${order.id}`}
      className={cn(
        'block rounded-2xl bg-vygo-card border border-vygo-border p-4 hover:border-vygo-green/30 transition-all duration-200 active:scale-[0.99]',
        className
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <PlatformBadge platform={order.platform} />
          <span className="text-xs text-vygo-secondary">#{order.orderNumber}</span>
          {stopNumber && (
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-vygo-green text-vygo-bg text-[10px] font-bold">
              {stopNumber}
            </span>
          )}
        </div>
        <span className="text-lg font-bold text-vygo-green text-money">
          {formatCurrency(order.earnings)}
        </span>
      </div>

      {!compact && (
        <div className="space-y-2 mb-3">
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-vygo-warning mt-1 flex-shrink-0" />
            <div>
              <p className="text-xs text-vygo-secondary leading-tight">{order.pickup.name}</p>
              <p className="text-sm text-vygo-white font-medium leading-tight">{order.pickup.address}</p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-vygo-green mt-1 flex-shrink-0" />
            <p className="text-sm text-vygo-white font-medium leading-tight">{order.dropoff.address}</p>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 text-xs text-vygo-secondary">
        <span className="flex items-center gap-1">
          <MapPin size={11} />
          {order.pickupDistanceKm !== undefined ? `A ${order.pickupDistanceKm} km · ${formatDistance(order.distanceKm)}` : formatDistance(order.distanceKm)}
        </span>
        <span className="flex items-center gap-1">
          <Clock size={11} />
          {formatMinutes(order.estimatedMinutes)}
        </span>
        <span className="ml-auto">
          <ArrowRight size={14} className="text-vygo-secondary" />
        </span>
      </div>
    </Link>
  )
}
