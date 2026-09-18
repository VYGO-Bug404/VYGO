import { useState } from 'react'
import { TrendingUp, Clock, Navigation2, Star } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EarningsChart } from '@/components/earnings/EarningsChart'
import { PlatformBadge } from '@/components/PlatformBadge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { earningsService } from '@/services/earnings.service'
import { useDriverStore } from '@/stores/driver.store'
import { useOrdersStore } from '@/stores/orders.store'
import { buildEarningsSummary, getTodayRange } from '@/lib/earningsAggregation'

import { formatCurrency, formatDistance, formatMinutes } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { Platform } from '@/types/order'

export function EarningsPage() {
  const [period, setPeriod] = useState<'today' | 'week' | 'month'>('today')
  const shiftStartedAt = useDriverStore((s) => s.shiftStartedAt)
  const vygoGainMxn = useDriverStore((s) => s.vygoGainMxn)
  const vygoKmSaved = useDriverStore((s) => s.vygoKmSaved)
  const vygoMinutesSaved = useDriverStore((s) => s.vygoMinutesSaved)
  const completedOrdersList = useOrdersStore((s) => s.completedOrders)

  const elapsedHours = shiftStartedAt
    ? Math.max((Date.now() - shiftStartedAt.getTime()) / 3_600_000, 0)
    : undefined

  const summary = period === 'today'
    ? {
        ...buildEarningsSummary(completedOrdersList, getTodayRange(), { elapsedHours }),
        additionalEarningsFromVygo: vygoGainMxn,
        kmSaved: vygoKmSaved,
        minutesSaved: vygoMinutesSaved,
      }
    : earningsService.getSummary(period)

  const todayEarnings = summary.total
  const completedOrders = summary.totalOrders
  const lifetimeTotal = completedOrdersList.reduce((s, o) => s + o.earnings, 0)
  const lifetimeCount = completedOrdersList.length

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
                  {lifetimeCount > 0 && (
                    <div className="bg-vygo-card-2 border border-vygo-border rounded-xl p-4 text-center">
                      <p className="text-sm text-vygo-white font-semibold">
                        Llevas {formatCurrency(lifetimeTotal)} en {lifetimeCount} {lifetimeCount === 1 ? 'entrega' : 'entregas'} en total
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Empty state for week/month */}
              {p !== 'today' && summary.total === 0 && (
                <div className="bg-vygo-card border border-vygo-border rounded-2xl p-8 text-center mb-4">
                  <p className="text-vygo-secondary text-sm">Sin entregas registradas en este periodo</p>
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

              {/* VYGO value — solo aplica a "hoy": no hay historial diario de rechazos para semana/mes */}
              {p === 'today' && (
                <div className="bg-vygo-green/5 border border-vygo-green/20 rounded-2xl p-4 mb-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Star size={14} className="text-vygo-green" />
                    <p className="text-sm font-semibold text-vygo-white">Gracias a VYGO</p>
                  </div>
                  {summary.additionalEarningsFromVygo === 0 && summary.kmSaved === 0 && summary.minutesSaved === 0 ? (
                    <p className="text-xs text-vygo-secondary/60 text-center py-1">
                      Aún no rechazas ofertas hoy
                    </p>
                  ) : (
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
                  )}
                </div>
              )}

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
