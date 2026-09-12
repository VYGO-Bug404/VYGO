import { cn } from '@/lib/utils'
import type { Platform } from '@/types/order'

const PLATFORM_CONFIG: Record<Platform, { label: string; className: string; dot: string }> = {
  uber: {
    label: 'Uber',
    className: 'bg-white/10 text-white border-white/20',
    dot: 'bg-white',
  },
  rappi: {
    label: 'Rappi',
    className: 'bg-red-500/15 text-red-400 border-red-500/20',
    dot: 'bg-red-500',
  },
  didi: {
    label: 'DiDi',
    className: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
    dot: 'bg-orange-500',
  },
}

interface PlatformBadgeProps {
  platform: Platform
  size?: 'sm' | 'md' | 'lg'
  showDot?: boolean
  className?: string
}

export function PlatformBadge({ platform, size = 'md', showDot = true, className }: PlatformBadgeProps) {
  const config = PLATFORM_CONFIG[platform] ?? {
    label: platform,
    className: 'bg-vygo-card-2 text-vygo-secondary border-vygo-border',
    dot: 'bg-vygo-secondary',
  }

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-[10px] gap-1',
    md: 'px-2.5 py-1 text-xs gap-1.5',
    lg: 'px-3 py-1.5 text-sm gap-2',
  }

  const dotSizes = {
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
    lg: 'w-2.5 h-2.5',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-semibold',
        config.className,
        sizeClasses[size],
        className
      )}
    >
      {showDot && (
        <span className={cn('rounded-full flex-shrink-0', config.dot, dotSizes[size])} />
      )}
      {config.label}
    </span>
  )
}
