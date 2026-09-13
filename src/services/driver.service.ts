import type { Driver } from '@/types/driver'
import { ordersService } from './orders.service'

export const driverService = {
  getDriver(): Driver {
    return {
      id: 'driver-local',
      name: 'Repartidor',       // overridden by auth.fullName at runtime
      avatarInitials: 'R',
      vehicle: { type: 'moto', brand: '', model: '' },
      platforms: [],
      rating: 0,
      totalDeliveries: 0,
      memberSince: '',
    }
  },

  getTodayEarnings(): number {
    // Seed from completed orders history so the store is in sync from the start
    const completed = ordersService.getCompletedOrders()
    return completed.reduce((sum, o) => sum + (o.earnings ?? 0), 0)
  },

  getEarningsPerHour(): number {
    const completed = ordersService.getCompletedOrders()
    if (completed.length === 0) return 0
    // Estimate: assume ~25 min per order on average
    const hoursEstimated = (completed.length * 25) / 60
    const totalEarnings = completed.reduce((sum, o) => sum + (o.earnings ?? 0), 0)
    return Math.round(totalEarnings / Math.max(hoursEstimated, 0.1))
  },

  getCompletedOrdersCount(): number {
    return ordersService.getCompletedOrders().length
  },
}
