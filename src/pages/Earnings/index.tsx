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
  const shiftStartedAt = useDriverStore((s) => s.shiftStartedAt)
  const vygoGainMxn = useDriverStore((s) => s.vygoGainMxn)
  const vygoKmSaved = useDriverStore((s) => s.vygoKmSaved)
  const vygoMinutesSaved = useDriverStore((s) => s.vygoMinutesSaved)
  const completedOrdersList = useOrdersStore((s) => s.completedOrders)

  // ── Cálculos reales para "Hoy" desde los pedidos completados ────────────────
  const totalKm = completedOrdersList.reduce((s, o) => s + o.distanceKm, 0)
  const perKm = totalKm > 0 ? todayEarnings / totalKm : 0

  // Agrupar ganancias por hora usando deliveredAt
  const hourMap: Record<number, { earnings: number; orders: number }> = {}
  for (const o of completedOrdersList) {
    if (!o.deliveredAt) continue
    const h = o.deliveredAt.getHours()
    if (!hourMap[h]) hourMap[h] = { earnings: 0, orders: 0 }
    hourMap[h].earnings += o.earnings
    hourMap[h].orders += 1
  }
  const hourly = Object.entries(hourMap)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([hour, d]) => {
      const h = Number(hour)
      return { hour: h, label: `${h % 12 || 12}${h < 12 ? 'AM' : 'PM'}`, earnings: d.earnings, orders: d.orders }
    })
  const bestHour = hourly.reduce(
    (best, h) => (h.earnings > best.earnings ? h : best),
    { hour: 0, label: '', earnings: 0, orders: 0 }
  )
  const bestHourRange = bestHour.earnings > 0 ? `${bestHour.label} – ${(bestHour.hour + 1) % 24}:00` : '—'

  // B1 baseline ($102/h) para comparativa VYGO
  const B1_RATE = 102
  const horasWorked = shiftStartedAt
    ? Math.max((Date.now() - shiftStartedAt.getTime()) / 3_600_000, 0.01)
    : (completedOrders > 0 ? completedOrders * 0.3 : 0)
  const b1Estimated = Math.round(B1_RATE * horasWorked)
  const b1Gain = Math.max(0, todayEarnings - b1Estimated)

  // Usar ganancia real de VYGO (rechazos correctos) si supera estimado B1
  const additionalEarnings = Math.max(vygoGainMxn, b1Gain)
  const kmSaved = vygoKmSaved > 0 ? vygoKmSaved : Math.round(completedOrders * 2.1)
  const minutesSaved = vygoMinutesSaved > 0 ? vygoMinutesSaved : Math.round(completedOrders * 8)
  const pctMejora = b1Estimated > 0
    ? Math.round(((todayEarnings - b1Estimated) / b1Estimated) * 100)
    : 0

  const mockSummary = earningsService.getSummary(period)

  const summary = period === 'today'
    ? {
        ...mockSummary,
        total: todayEarnings,
        perHour: earningsPerHour,
        perKm: Math.round(perKm * 10) / 10,
        totalKm: Math.round(totalKm * 10) / 10,
        totalOrders: completedOrders,
        hourly,
        bestHourRange,
        bestHourEarnings: bestHour.earnings,
        additionalEarningsFromVygo: additionalEarnings,
        kmSaved,
        minutesSaved,
        byPlatform: completedOrdersList.length > 0
          ? buildPlatformBreakdown(completedOrdersList)
          : [],
      }
    : mockSummary

  const vygoImpactPct = pctMejora

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

              {/* Empty state — today sin datos */}
              {p === 'today' && todayEarnings === 0 && completedOrders === 0 && (
                <div className="bg-vygo-card border border-vygo-border rounded-2xl p-8 text-center">
                  <div className="w-14 h-14 rounded-full bg-vygo-green/10 border border-vygo-green/20 flex items-center justify-center mx-auto mb-4">
                    <TrendingUp size={24} className="text-vygo-green" />
                  </div>
                  <p className="text-vygo-white font-semibold text-base mb-1">Aún no hay ganancias hoy</p>
                  <p className="text-vygo-secondary text-sm mb-4">
                    Inicia una jornada y acepta pedidos para ver tus resultados aquí.
                  </p>
                  <div className="bg-vygo-card-2 border border-vygo-border rounded-xl p-4 text-left space-y-2">
                    <p className="text-xs text-vygo-secondary font-semibold uppercase tracking-widest mb-2">Benchmark del sistema</p>
                    <div className="flex justify-between text-sm">
                      <span className="text-vygo-secondary">Sin VYGO (B1)</span>
                      <span className="text-vygo-white font-semibold">$102/h</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-vygo-secondary">VYGO regla (B2)</span>
                      <span className="text-vygo-white font-semibold">$158/h</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-vygo-secondary">VYGO agente (PPO)</span>
                      <span className="text-vygo-green font-bold">$169/h ↑</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Empty state for week/month */}
              {p !== 'today' && summary.total === 0 && (
                <div className="bg-vygo-card border border-vygo-border rounded-2xl p-8 text-center mb-4">
                  <p className="text-vygo-secondary text-sm">Datos históricos próximamente</p>
                  <p className="text-vygo-secondary/50 text-xs mt-1">Se conectarán desde el backend</p>
                </div>
              )}

              {/* Contenido con datos — oculto si today sin actividad */}
              {(p !== 'today' || todayEarnings > 0 || completedOrders > 0) && <>

              {/* Hero earnings */}
              <div className="bg-vygo-card border border-vygo-border rounded-2xl p-5 mb-4">
                <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide mb-1">
                  Ganancia {p === 'today' ? 'hoy' : p === 'week' ? 'esta semana' : 'este mes'}
                </p>
                <div className="flex items-end gap-3 mb-3">
                  <span className="text-4xl font-bold text-vygo-green text-money">
                    {formatCurrency(summary.total)}
                  </span>
                  {p === 'today' && summary.perHour > 0 && (
                    <span className="flex items-center gap-1 text-sm font-semibold rounded-full px-2 py-0.5 mb-1 bg-vygo-green/15 text-vygo-green">
                      <TrendingUp size={12} />
                      ${summary.perHour}/h
                    </span>
                  )}
                </div>
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
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Star size={14} className="text-vygo-green" />
                    <p className="text-sm font-semibold text-vygo-white">Gracias a VYGO</p>
                  </div>
                  {p === 'today' && vygoImpactPct > 0 && (
                    <span className="text-xs font-bold text-vygo-green bg-vygo-green/10 px-2 py-0.5 rounded-full">
                      +{vygoImpactPct}% vs sin VYGO
                    </span>
                  )}
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

                {summary.byPlatform.length === 0 ? (
                  <p className="text-xs text-vygo-secondary/60 text-center py-3">
                    {p === 'today' ? 'Completa pedidos para ver el desglose' : 'Sin datos históricos aún'}
                  </p>
                ) : (
                  <div className="space-y-3">
                    {summary.byPlatform
                      .sort((a, b) => b.earningsPerKm - a.earningsPerKm)
                      .map((plat, i) => {
                        const maxEarnings = Math.max(...summary.byPlatform.map((x) => x.totalEarnings))
                        const barWidth = maxEarnings > 0 ? (plat.totalEarnings / maxEarnings) * 100 : 0
                        return (
                          <div key={plat.platform}>
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-2">
                                <PlatformBadge platform={plat.platform as Platform} size="sm" />
                                {i === 0 && (
                                  <span className="text-[9px] font-semibold text-vygo-green bg-vygo-green/10 px-1.5 py-0.5 rounded-full">
                                    Más rentable
                                  </span>
                                )}
                              </div>
                              <div className="text-right">
                                <p className="text-sm font-bold text-vygo-white text-money">{formatCurrency(plat.totalEarnings)}</p>
                                <p className="text-[10px] text-vygo-secondary">${plat.earningsPerKm.toFixed(2)}/km</p>
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
                )}
              </div>

              </> /* fin bloque con datos */}
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
