import { create } from 'zustand'
import type { DriverState, DriverStatus } from '@/types/driver'
import { driverService } from '@/services/driver.service'

interface DriverStore extends Omit<DriverState, 'activeMinutes'> {
  startShift: () => void
  endShift: () => void
  setStatus: (status: DriverStatus) => void
  addEarnings: (amount: number) => void
  incrementCompletedOrders: () => void
}

export const useDriverStore = create<DriverStore>((set, get) => ({
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

  addEarnings: (amount: number) =>
    set((state) => {
      const newEarnings = state.todayEarnings + amount
      const shiftMinutes = state.shiftStartedAt
        ? (Date.now() - state.shiftStartedAt.getTime()) / 60000
        : 60
      const newPerHour = Math.round(newEarnings / Math.max(shiftMinutes / 60, 0.25))
      return { todayEarnings: newEarnings, earningsPerHour: newPerHour }
    }),

  incrementCompletedOrders: () =>
    set((state) => ({ completedOrders: state.completedOrders + 1 })),
}))
