import { cn } from '@/lib/utils'
import type { HourlyEarning } from '@/types/earnings'

interface EarningsChartProps {
  data: HourlyEarning[]
  className?: string
}

export function EarningsChart({ data, className }: EarningsChartProps) {
  const maxEarnings = Math.max(...data.map((d) => d.earnings), 1)

  return (
    <div className={cn('', className)}>
      <div className="flex items-end justify-between gap-1.5 h-24">
        {data.map((item) => {
          const heightPct = item.earnings > 0 ? (item.earnings / maxEarnings) * 100 : 4
          const isTop = item.earnings === maxEarnings && item.earnings > 0

          return (
            <div key={item.hour} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full relative rounded-t-lg transition-all duration-700"
                style={{ height: `${heightPct}%` }}
              >
                {item.earnings > 0 ? (
                  <div
                    className={cn(
                      'absolute inset-0 rounded-t-lg',
                      isTop ? 'bg-vygo-green' : 'bg-vygo-green/40'
                    )}
                  />
                ) : (
                  <div className="absolute inset-0 rounded-t-lg bg-vygo-border/40" />
                )}
              </div>
              <span className="text-[9px] text-vygo-secondary font-medium">{item.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
