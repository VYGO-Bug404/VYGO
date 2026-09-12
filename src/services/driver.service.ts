import type { Driver } from '@/types/driver'

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

  getTodayEarnings(): number { return 0 },
  getEarningsPerHour(): number { return 0 },
  getCompletedOrdersCount(): number { return 0 },
}
