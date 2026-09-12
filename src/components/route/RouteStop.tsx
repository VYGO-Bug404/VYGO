import { Check, MapPin, Navigation } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatTime } from '@/lib/utils'
import { PlatformBadge } from '@/components/PlatformBadge'
import type { RouteStop as RouteStopType } from '@/types/route'

interface RouteStopProps {
  stop: RouteStopType
  isActive: boolean
  isLast: boolean
  className?: string
}

export function RouteStop({ stop, isActive, isLast, className }: RouteStopProps) {
  const { order, type, completed, estimatedArrival, stopNumber } = stop

  return (
    <div className={cn('flex gap-3', className)}>
      <div className="flex flex-col items-center">
        <div
          className={cn(
            'w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all duration-300',
            completed
              ? 'bg-vygo-green border-vygo-green'
              : isActive
              ? 'bg-vygo-green/15 border-vygo-green animate-pulse'
              : 'bg-vygo-card-2 border-vygo-border'
          )}
        >
          {completed ? (
            <Check size={14} className="text-vygo-bg" />
          ) : type === 'pickup' ? (
            <MapPin size={12} className={isActive ? 'text-vygo-green' : 'text-vygo-secondary'} />
          ) : (
            <Navigation size={12} className={isActive ? 'text-vygo-green' : 'text-vygo-secondary'} />
          )}
        </div>
        {!isLast && (
          <div
            className={cn(
              'w-0.5 flex-1 min-h-[32px] mt-1 rounded-full',
              completed ? 'bg-vygo-green' : 'bg-vygo-border'
            )}
          />
        )}
      </div>

      <div className="flex-1 pb-4">
        <div className="flex items-start justify-between mb-1">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'text-xs font-medium uppercase tracking-wide',
                type === 'pickup' ? 'text-vygo-warning' : 'text-vygo-green'
              )}
            >
              {type === 'pickup' ? 'Recoger' : 'Entregar'}
            </span>
            <PlatformBadge platform={order.platform} size="sm" showDot={false} />
            <span className="text-[10px] text-vygo-secondary">#{order.orderNumber}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-4 h-4 flex items-center justify-center rounded-full bg-vygo-green/15 text-[9px] font-bold text-vygo-green">
              {stopNumber}
            </span>
          </div>
        </div>

        <p className="text-sm font-semibold text-vygo-white leading-tight">
          {type === 'pickup' ? order.pickup.address : order.dropoff.address}
        </p>
        <p className="text-xs text-vygo-secondary">
          {type === 'pickup' ? order.pickup.neighborhood : order.dropoff.neighborhood}
        </p>

        {isActive && (
          <p className="text-xs text-vygo-green mt-1 font-medium">
            Llegada estimada · {formatTime(estimatedArrival)}
          </p>
        )}
      </div>
    </div>
  )
}
