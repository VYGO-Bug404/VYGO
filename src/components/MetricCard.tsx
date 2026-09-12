import { cn } from '@/lib/utils'

interface MetricCardProps {
  value: string
  label: string
  highlight?: boolean
  className?: string
  suffix?: string
  trend?: 'up' | 'down' | 'neutral'
}

export function MetricCard({ value, label, highlight = false, className, trend }: MetricCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-2xl p-3 gap-0.5 bg-vygo-card border border-vygo-border',
        highlight && 'border-vygo-green/30 bg-vygo-green/5',
        className
      )}
    >
      <span
        className={cn(
          'text-xl font-bold leading-tight text-money',
          highlight ? 'text-vygo-green' : 'text-vygo-white'
        )}
      >
        {value}
      </span>
      <span className="text-[11px] text-vygo-secondary font-medium">{label}</span>
      {trend === 'up' && <span className="text-[10px] text-vygo-green font-semibold">↑</span>}
      {trend === 'down' && <span className="text-[10px] text-vygo-danger font-semibold">↓</span>}
    </div>
  )
}
