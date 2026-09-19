import { cn } from '@/lib/utils'
import type { HourlyEarning } from '@/types/earnings'

interface EarningsChartProps {
  data: HourlyEarning[]
  className?: string
}

export function EarningsChart({ data, className }: EarningsChartProps) {
  const numericValues = data.map((d) => Number(d.earnings) || 0)
  const maxEarnings = Math.max(...numericValues, 1)

  return (
    <div className={cn('', className)}>
      <div className="flex items-end justify-between gap-1.5 h-24">
        {data.map((item, idx) => {
          const val = numericValues[idx]
          const heightPct = val > 0 ? (val / maxEarnings) * 100 : 4
          const isTop = val === maxEarnings && val > 0

          return (
            <div key={item.hour} className="flex-1 flex flex-col items-center gap-1 h-full">
              <div className="flex-1 w-full flex items-end">
                <div
                  className={cn(
                    'w-full rounded-t-lg transition-all duration-700',
                    val > 0
                      ? isTop
                        ? 'bg-vygo-green'
                        : 'bg-vygo-green/40'
                      : 'bg-vygo-border/40'
                  )}
                  style={{ height: `${Math.max(heightPct, 8)}%` }}
                />
              </div>
              <span className="text-[9px] text-vygo-secondary font-medium">{item.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
