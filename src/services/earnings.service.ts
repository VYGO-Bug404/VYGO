import type { EarningsSummary } from '@/types/earnings'
import { useOrdersStore } from '@/stores/orders.store'
import { buildEarningsSummary, getTodayRange, getWeekRange, getMonthRange } from '@/lib/earningsAggregation'

export const earningsService = {
  getSummary(period: 'today' | 'week' | 'month' = 'today'): EarningsSummary {
    const orders = useOrdersStore.getState().completedOrders
    const range = period === 'today' ? getTodayRange() : period === 'week' ? getWeekRange() : getMonthRange()
    return buildEarningsSummary(orders, range)
  },
}
