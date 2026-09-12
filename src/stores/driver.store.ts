import { create } from 'zustand'
import type { DriverState } from '@/types/driver'
import { driverService } from '@/services/driver.service'

interface DriverStore extends DriverState {
  startShift: () => void
  endShift: () => void
  addEarnings: (amount: number) => void
  incrementCompletedOrders: () => void
}

export const useDriverStore = create<DriverStore>((set) => ({
  driver: driverService.getDriver(),
  status: 'offline',
  todayEarnings: driverService.getTodayEarnings(),
  earningsPerHour: driverService.getEarningsPerHour(),
  completedOrders: driverService.getCompletedOrdersCount(),
  shiftStartedAt: null,
  activeMinutes: 0,

  startShift: () =>
    set({
      status: 'active_route',
      shiftStartedAt: new Date(),
    }),

  endShift: () =>
    set({
      status: 'offline',
      shiftStartedAt: null,
    }),

  addEarnings: (amount) =>
    set((state) => ({
      todayEarnings: state.todayEarnings + amount,
    })),

  incrementCompletedOrders: () =>
    set((state) => ({
      completedOrders: state.completedOrders + 1,
    })),
}))
