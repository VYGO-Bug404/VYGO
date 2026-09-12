import { create } from 'zustand'
import type { DriverState, DriverStatus } from '@/types/driver'
import { driverService } from '@/services/driver.service'
import { useAuthStore } from '@/stores/auth.store'

interface DriverStore extends Omit<DriverState, 'activeMinutes'> {
  startShift: () => void
  endShift: () => void
  setStatus: (status: DriverStatus) => void
  addEarnings: (amount: number) => void
  incrementCompletedOrders: () => void
  syncTelemetria: (t: { rho_actual_mxn_h: number; ganancia_turno_mxn: number; pedidos_entregados: number }) => void
  syncName: () => void
}

function getInitialDriver() {
  const base = driverService.getDriver()
  const auth = useAuthStore.getState()
  const fullName = auth.fullName
  if (!fullName) return base
  const parts = fullName.trim().split(' ')
  return {
    ...base,
    name: parts[0],
    avatarInitials: parts.map((p) => p[0]).slice(0, 2).join('').toUpperCase(),
  }
}

export const useDriverStore = create<DriverStore>((set, get) => ({
  driver: getInitialDriver(),
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
      todayEarnings: 0,
      earningsPerHour: 0,
      completedOrders: 0,
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

  syncTelemetria: (telemetria: { rho_actual_mxn_h: number; ganancia_turno_mxn: number; pedidos_entregados: number }) =>
    set((state) => ({
      todayEarnings: telemetria.ganancia_turno_mxn,
      earningsPerHour: telemetria.rho_actual_mxn_h,
      completedOrders: telemetria.pedidos_entregados,
    })),

  syncName: () => {
    const auth = useAuthStore.getState()
    const fullName = auth.fullName
    if (!fullName) return
    const parts = fullName.trim().split(' ')
    set((state) => ({
      driver: {
        ...state.driver,
        name: parts[0],
        avatarInitials: parts.map((p) => p[0]).slice(0, 2).join('').toUpperCase(),
      },
    }))
  },
}))
