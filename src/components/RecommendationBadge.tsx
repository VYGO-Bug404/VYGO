import { TrendingUp, Minus, TrendingDown, Zap, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Recommendation } from '@/types/order'

const CONFIG: Record<Recommendation, {
  label: string
  className: string
  Icon: LucideIcon
}> = {
  excellent: {
    label: 'Muy rentable',
    className: 'bg-vygo-green/15 text-vygo-green border-vygo-green/20',
    Icon: Zap,
  },
  good: {
    label: 'Rentable',
    className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    Icon: TrendingUp,
  },
  neutral: {
    label: 'Neutral',
    className: 'bg-vygo-secondary/15 text-vygo-secondary border-vygo-secondary/20',
    Icon: Minus,
  },
  bad: {
    label: 'No recomendado',
    className: 'bg-vygo-danger/15 text-vygo-danger border-vygo-danger/20',
    Icon: TrendingDown,
  },
}

interface RecommendationBadgeProps {
  recommendation: Recommendation
  className?: string
}

export function RecommendationBadge({ recommendation, className }: RecommendationBadgeProps) {
  const config = CONFIG[recommendation]
  const { Icon } = config

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold',
        config.className,
        className
      )}
    >
      <Icon size={12} />
      {config.label}
    </span>
  )
}
