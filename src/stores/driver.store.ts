import { create } from 'zustand'
import type { DriverState, DriverStatus } from '@/types/driver'
import { driverService } from '@/services/driver.service'

interface DriverStore extends Omit<DriverState, 'activeMinutes'> {
  startShift: () => void
  endShift: () => void
  setStatus: (status: DriverStatus) => void
}

export const useDriverStore = create<DriverStore>((set) => ({
  driver: driverService.getDriver(),
  status: 'offline',
  todayEarnings: driverService.getTodayEarnings(),
  earningsPerHour: driverService.getEarningsPerHour(),
  completedOrders: driverService.getCompletedOrdersCount(),
  shiftStartedAt: null,

  startShift: () =>
    set({
      status: 'online',
      shiftStartedAt: new Date(),
    }),

  endShift: () =>
    set({
      status: 'offline',
      shiftStartedAt: null,
    }),

  setStatus: (status) => set({ status }),
}))
