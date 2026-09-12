import { useState } from 'react'
import { TrendingUp, Clock, Navigation2, Star } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EarningsChart } from '@/components/earnings/EarningsChart'
import { PlatformBadge } from '@/components/PlatformBadge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { earningsService } from '@/services/earnings.service'
import { useDriverStore } from '@/stores/driver.store'
import { useOrdersStore } from '@/stores/orders.store'
import { formatCurrency, formatDistance, formatMinutes } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { Platform, Order } from '@/types/order'
import type { PlatformEarning } from '@/types/earnings'

export function EarningsPage() {
  const [period, setPeriod] = useState<'today' | 'week' | 'month'>('today')
  const todayEarnings = useDriverStore((s) => s.todayEarnings)
  const earningsPerHour = useDriverStore((s) => s.earningsPerHour)
  const completedOrders = useDriverStore((s) => s.completedOrders)
  const completedOrdersList = useOrdersStore((s) => s.completedOrders)

  const mockSummary = earningsService.getSummary(period)

  // For "today", use live store data; week/month use mock data
  const summary = period === 'today'
    ? {
        ...mockSummary,
        total: todayEarnings,
        perHour: earningsPerHour,
        totalOrders: completedOrders,
        // Recalculate platform breakdown from completed orders if we have any real ones
        byPlatform: completedOrdersList.length > 0
          ? buildPlatformBreakdown(completedOrdersList)
          : mockSummary.byPlatform,
      }
    : mockSummary

  const changeIsPositive = summary.changePercent >= 0

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader title="Ganancias" />

      <div className="px-4 pb-8 space-y-4">
        {/* Period tabs */}
        <Tabs value={period} onValueChange={(v) => setPeriod(v as typeof period)}>
          <TabsList className="w-full">
            <TabsTrigger value="today" className="flex-1">Hoy</TabsTrigger>
            <TabsTrigger value="week" className="flex-1">Semana</TabsTrigger>
            <TabsTrigger value="month" className="flex-1">Mes</TabsTrigger>
          </TabsList>

          {(['today', 'week', 'month'] as const).map((p) => (
            <TabsContent key={p} value={p}>
              {/* Hero earnings */}
              <div className="bg-vygo-card border border-vygo-border rounded-2xl p-5 mb-4">
                <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide mb-1">
                  Ganancia {p === 'today' ? 'hoy' : p === 'week' ? 'esta semana' : 'este mes'}
                </p>
                <div className="flex items-end gap-3 mb-3">
                  <span className="text-4xl font-bold text-vygo-green text-money">
                    {formatCurrency(summary.total)}
                  </span>
                  <span
                    className={cn(
                      'flex items-center gap-1 text-sm font-semibold rounded-full px-2 py-0.5 mb-1',
                      changeIsPositive
                        ? 'bg-vygo-green/15 text-vygo-green'
                        : 'bg-vygo-danger/15 text-vygo-danger'
                    )}
                  >
                    <TrendingUp size={12} />
                    {changeIsPositive ? '+' : ''}{summary.changePercent.toFixed(1)}%
                  </span>
                </div>
                <p className="text-xs text-vygo-secondary">
                  vs {p === 'today' ? 'ayer' : p === 'week' ? 'semana anterior' : 'mes anterior'}
                </p>
              </div>

              {/* Chart */}
              {p === 'today' && (
                <div className="bg-vygo-card border border-vygo-border rounded-2xl p-4 mb-4">
                  <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide mb-3">
                    Por hora
                  </p>
                  <EarningsChart data={summary.hourly} />
                </div>
              )}

              {/* Key metrics */}
              <div className="grid grid-cols-3 gap-2 mb-4">
                <EarningMetric
                  value={`$${summary.perHour}/h`}
                  label="Por hora"
                  highlight
                />
                <EarningMetric
                  value={`$${summary.perKm.toFixed(0)}/km`}
                  label="Por km"
                />
                <EarningMetric
                  value={String(summary.totalOrders)}
                  label={summary.totalOrders === 1 ? 'Entrega' : 'Entregas'}
                />
              </div>

              {/* VYGO value */}
              <div className="bg-vygo-green/5 border border-vygo-green/20 rounded-2xl p-4 mb-4">
                <div className="flex items-center gap-2 mb-3">
                  <Star size={14} className="text-vygo-green" />
                  <p className="text-sm font-semibold text-vygo-white">Gracias a VYGO</p>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div>
                    <p className="text-xl font-bold text-vygo-green text-money">
                      {formatCurrency(summary.additionalEarningsFromVygo)}
                    </p>
                    <p className="text-[10px] text-vygo-secondary mt-0.5 leading-tight">
                      ganancia adicional estimada
                    </p>
                  </div>
                  <div className="border-x border-vygo-border/50">
                    <p className="text-xl font-bold text-vygo-white">
                      {formatDistance(summary.kmSaved)}
                    </p>
                    <p className="text-[10px] text-vygo-secondary mt-0.5 leading-tight">
                      km ahorrados
                    </p>
                  </div>
                  <div>
                    <p className="text-xl font-bold text-vygo-white">
                      {formatMinutes(summary.minutesSaved)}
                    </p>
                    <p className="text-[10px] text-vygo-secondary mt-0.5 leading-tight">
                      tiempo ahorrado
                    </p>
                  </div>
                </div>
              </div>

              {/* Best hour */}
              <div className="bg-vygo-card border border-vygo-border rounded-2xl p-4 mb-4">
                <div className="flex items-center gap-2 mb-1">
                  <Clock size={13} className="text-vygo-secondary" />
                  <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide">
                    Mejor horario
                  </p>
                </div>
                <p className="text-base font-semibold text-vygo-white">{summary.bestHourRange}</p>
                <p className="text-sm text-vygo-green font-bold text-money mt-0.5">${summary.bestHourEarnings}/h</p>
              </div>

              {/* Platform breakdown */}
              <div className="bg-vygo-card border border-vygo-border rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Navigation2 size={13} className="text-vygo-secondary" />
                  <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide">
                    Por plataforma
                  </p>
                </div>

                <div className="space-y-3">
                  {summary.byPlatform
                    .sort((a, b) => b.earningsPerKm - a.earningsPerKm)
                    .map((p, i) => {
                      const maxEarnings = Math.max(...summary.byPlatform.map((x) => x.totalEarnings))
                      const barWidth = (p.totalEarnings / maxEarnings) * 100
                      return (
                        <div key={p.platform}>
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <PlatformBadge platform={p.platform as Platform} size="sm" />
                              {i === 0 && (
                                <span className="text-[9px] font-semibold text-vygo-green bg-vygo-green/10 px-1.5 py-0.5 rounded-full">
                                  Más rentable
                                </span>
                              )}
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-bold text-vygo-white text-money">{formatCurrency(p.totalEarnings)}</p>
                              <p className="text-[10px] text-vygo-secondary">${p.earningsPerKm.toFixed(2)}/km</p>
                            </div>
                          </div>
                          <div className="h-1.5 bg-vygo-border rounded-full overflow-hidden">
                            <div
                              className="h-full bg-vygo-green rounded-full transition-all duration-700"
                              style={{ width: `${barWidth}%`, opacity: i === 0 ? 1 : 0.5 }}
                            />
                          </div>
                        </div>
                      )
                    })}
                </div>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </div>
  )
}

function buildPlatformBreakdown(orders: Order[]): PlatformEarning[] {
  const map: Record<string, { earnings: number; km: number; count: number }> = {}
  for (const o of orders) {
    if (!map[o.platform]) map[o.platform] = { earnings: 0, km: 0, count: 0 }
    map[o.platform].earnings += o.earnings
    map[o.platform].km += o.distanceKm
    map[o.platform].count += 1
  }
  return Object.entries(map).map(([platform, d]) => ({
    platform,
    totalEarnings: d.earnings,
    totalOrders: d.count,
    earningsPerKm: d.km > 0 ? d.earnings / d.km : 0,
    avgPerOrder: d.count > 0 ? d.earnings / d.count : 0,
  }))
}

function EarningMetric({ value, label, highlight = false }: { value: string; label: string; highlight?: boolean }) {
  return (
    <div className={cn(
      'rounded-2xl p-3 text-center border',
      highlight ? 'bg-vygo-green/5 border-vygo-green/20' : 'bg-vygo-card border-vygo-border'
    )}>
      <p className={cn('text-base font-bold leading-tight text-money', highlight ? 'text-vygo-green' : 'text-vygo-white')}>
        {value}
      </p>
      <p className="text-[10px] text-vygo-secondary mt-0.5">{label}</p>
    </div>
  )
}
