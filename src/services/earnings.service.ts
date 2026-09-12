import type { EarningsSummary } from '@/types/earnings'

const EMPTY: EarningsSummary = {
  total: 0,
  perHour: 0,
  perKm: 0,
  totalOrders: 0,
  changePercent: 0,
  activeMinutes: 0,
  totalKm: 0,
  hourly: [],
  byPlatform: [],
  bestHourRange: '—',
  bestHourEarnings: 0,
  additionalEarningsFromVygo: 0,
  kmSaved: 0,
  minutesSaved: 0,
}

export const earningsService = {
  getSummary(_period: 'today' | 'week' | 'month' = 'today'): EarningsSummary {
    // week/month require historical data from backend — return empty until connected
    return EMPTY
  },
}
