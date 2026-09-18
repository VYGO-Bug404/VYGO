import type { Order } from '@/types/order'
import type { EarningsSummary, HourlyEarning, PlatformEarning } from '@/types/earnings'

export type DateRange = { start: Date; end: Date }

// entregado_en llega NULL en los pedidos sembrados en Supabase (bug de datos del seed) —
// createdAt sigue siendo una fecha real del pedido, así que sirve de respaldo razonable.
export function getOrderTimestamp(order: Order): Date {
  return order.deliveredAt ?? order.createdAt
}

function startOfDay(d: Date): Date {
  const copy = new Date(d)
  copy.setHours(0, 0, 0, 0)
  return copy
}

export function getTodayRange(now: Date = new Date()): DateRange {
  return { start: startOfDay(now), end: now }
}

export function getWeekRange(now: Date = new Date()): DateRange {
  const start = startOfDay(now)
  start.setDate(start.getDate() - 6)
  return { start, end: now }
}

export function getMonthRange(now: Date = new Date()): DateRange {
  const start = startOfDay(now)
  start.setDate(start.getDate() - 29)
  return { start, end: now }
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

function buildHourly(orders: Order[]): HourlyEarning[] {
  const hourMap: Record<number, { earnings: number; orders: number }> = {}
  for (const o of orders) {
    const h = getOrderTimestamp(o).getHours()
    if (!hourMap[h]) hourMap[h] = { earnings: 0, orders: 0 }
    hourMap[h].earnings += o.earnings
    hourMap[h].orders += 1
  }
  return Object.entries(hourMap)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([hour, d]) => {
      const h = Number(hour)
      return { hour: h, label: `${h % 12 || 12}${h < 12 ? 'AM' : 'PM'}`, earnings: d.earnings, orders: d.orders }
    })
}

export function buildEarningsSummary(
  orders: Order[],
  range: DateRange,
  opts: { elapsedHours?: number } = {}
): EarningsSummary {
  const filtered = orders.filter((o) => {
    const t = getOrderTimestamp(o).getTime()
    return t >= range.start.getTime() && t <= range.end.getTime()
  })

  const total = filtered.reduce((s, o) => s + o.earnings, 0)
  const totalKm = filtered.reduce((s, o) => s + o.distanceKm, 0)
  const totalMinutes = filtered.reduce((s, o) => s + o.estimatedMinutes, 0)

  // Usar el mayor entre el tiempo real transcurrido de jornada y el estimado por pedidos —
  // evita que $/h se dispare a un número absurdo justo al iniciar jornada (elapsedHours ~ 0)
  // cuando "hoy" ya incluye ganancia de antes de esta jornada.
  const hours = Math.max(opts.elapsedHours ?? 0, totalMinutes / 60)
  const perHour = hours > 0 ? Math.round(total / hours) : 0
  const perKm = totalKm > 0 ? total / totalKm : 0

  const hourly = buildHourly(filtered)
  const bestHour = hourly.reduce(
    (best, h) => (h.earnings > best.earnings ? h : best),
    { hour: 0, label: '', earnings: 0, orders: 0 }
  )
  const bestHourRange = bestHour.earnings > 0 ? `${bestHour.label} – ${(bestHour.hour + 1) % 24}:00` : '—'

  return {
    total,
    perHour,
    perKm: Math.round(perKm * 10) / 10,
    totalOrders: filtered.length,
    changePercent: 0, // no hay línea base histórica confiable para comparar todavía
    activeMinutes: totalMinutes,
    totalKm: Math.round(totalKm * 10) / 10,
    hourly,
    byPlatform: buildPlatformBreakdown(filtered),
    bestHourRange,
    bestHourEarnings: bestHour.earnings,
    additionalEarningsFromVygo: 0, // no derivable de pedidos — el caller la sobrepone solo para "hoy"
    kmSaved: 0,
    minutesSaved: 0,
  }
}
