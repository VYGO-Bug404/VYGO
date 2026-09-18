import { useMemo } from 'react'
import { useOrdersStore } from '@/stores/orders.store'
import { useDriverStore } from '@/stores/driver.store'
import { buildEarningsSummary, getTodayRange } from '@/lib/earningsAggregation'

export function useTodayMetrics() {
  const completedOrders = useOrdersStore((s) => s.completedOrders)
  const shiftStartedAt = useDriverStore((s) => s.shiftStartedAt)

  return useMemo(() => {
    const elapsedHours = shiftStartedAt
      ? Math.max((Date.now() - shiftStartedAt.getTime()) / 3_600_000, 0)
      : undefined
    const summary = buildEarningsSummary(completedOrders, getTodayRange(), { elapsedHours })
    return {
      todayEarnings: summary.total,
      earningsPerHour: summary.perHour,
      completedOrders: summary.totalOrders,
    }
  }, [completedOrders, shiftStartedAt])
}
