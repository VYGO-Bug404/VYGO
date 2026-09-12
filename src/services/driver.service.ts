import { MOCK_DRIVER } from './mock-data'
import type { Driver } from '@/types/driver'

export const driverService = {
  getDriver(): Driver {
    return MOCK_DRIVER
  },

  getTodayEarnings(): number {
    return 684
  },

  getEarningsPerHour(): number {
    return 192
  },

  getCompletedOrdersCount(): number {
    return 8
  },
}
