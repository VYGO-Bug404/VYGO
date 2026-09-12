import { MOCK_EARNINGS_SUMMARY } from './mock-data'
import type { EarningsSummary } from '@/types/earnings'

export const earningsService = {
  getSummary(_period: 'today' | 'week' | 'month' = 'today'): EarningsSummary {
    if (_period === 'week') {
      return {
        ...MOCK_EARNINGS_SUMMARY,
        total: 6840,
        perHour: 204,
        perKm: 17.8,
        totalOrders: 82,
        changePercent: 8.2,
        additionalEarningsFromVygo: 920,
        kmSaved: 118,
        minutesSaved: 223,
      }
    }
    if (_period === 'month') {
      return {
        ...MOCK_EARNINGS_SUMMARY,
        total: 28400,
        perHour: 198,
        perKm: 17.2,
        totalOrders: 340,
        changePercent: 14.7,
        additionalEarningsFromVygo: 3840,
        kmSaved: 480,
        minutesSaved: 940,
      }
    }
    return MOCK_EARNINGS_SUMMARY
  },
}
