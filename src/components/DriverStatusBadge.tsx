import { cn } from '@/lib/utils'
import type { DriverStatus } from '@/types/driver'

const STATUS_CONFIG: Partial<Record<DriverStatus, { label: string; className: string }>> = {
  online: { label: 'En línea', className: 'bg-vygo-green/15 text-vygo-green' },
  offline: { label: 'Desconectado', className: 'bg-vygo-secondary/15 text-vygo-secondary' },
  active_route: { label: 'En ruta', className: 'bg-vygo-green/15 text-vygo-green' },
  heading_to_pickup: { label: 'Recogiendo', className: 'bg-vygo-warning/15 text-vygo-warning' },
  pickup: { label: 'En pickup', className: 'bg-vygo-warning/15 text-vygo-warning' },
  delivery: { label: 'Entregando', className: 'bg-vygo-green/15 text-vygo-green' },
}

interface DriverStatusBadgeProps {
  status: DriverStatus
  showPulse?: boolean
  className?: string
}

export function DriverStatusBadge({ status, showPulse = true, className }: DriverStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? { label: status, className: 'bg-vygo-secondary/15 text-vygo-secondary' }
  const isOnline = status !== 'offline'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold',
        config.className,
        className
      )}
    >
      <span className="relative flex h-2 w-2">
        {showPulse && isOnline && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-vygo-green opacity-75" />
        )}
        <span className={cn('relative inline-flex rounded-full h-2 w-2', isOnline ? 'bg-vygo-green' : 'bg-vygo-secondary')} />
      </span>
      {config.label}
    </span>
  )
}
