import { create } from 'zustand'
import type { DriverState, DriverStatus } from '@/types/driver'
import { driverService } from '@/services/driver.service'
import { useAuthStore } from '@/stores/auth.store'

interface DriverStore extends Omit<DriverState, 'activeMinutes'> {
  _totalDeliveryMinutes: number
  vygoGainMxn: number
  vygoKmSaved: number
  vygoMinutesSaved: number
  startShift: () => void
  endShift: () => void
  setStatus: (status: DriverStatus) => void
  addEarnings: (amount: number, estimatedMinutes?: number) => void
  incrementCompletedOrders: () => void
  syncTelemetria: (t: { rho_actual_mxn_h: number; ganancia_turno_mxn: number; pedidos_entregados: number }) => void
  syncName: () => void
  addVygoGain: (gainMxn: number, kmSaved: number, minutesSaved: number) => void
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
  _totalDeliveryMinutes: 0,
  vygoGainMxn: 0,
  vygoKmSaved: 0,
  vygoMinutesSaved: 0,

  startShift: () =>
    set({
      status: 'online',
      shiftStartedAt: new Date(),
      // Reset session counters at the START of each new shift
      todayEarnings: 0,
      earningsPerHour: 0,
      completedOrders: 0,
      _totalDeliveryMinutes: 0,
      vygoGainMxn: 0,
      vygoKmSaved: 0,
      vygoMinutesSaved: 0,
    }),

  endShift: () =>
    set({
      // Keep earnings data visible after shift ends — resets on next startShift
      status: 'offline',
      shiftStartedAt: null,
    }),

  setStatus: (status) => set({ status }),

  addEarnings: (amount: number, estimatedMinutes = 0) =>
    set((state) => {
      const newEarnings = state.todayEarnings + amount
      const newDeliveryMinutes = state._totalDeliveryMinutes + estimatedMinutes
      // Use accumulated delivery time; floor at 30 min to avoid division by near-zero
      const newPerHour = Math.round(newEarnings / Math.max(newDeliveryMinutes / 60, 0.5))
      return { todayEarnings: newEarnings, earningsPerHour: newPerHour, _totalDeliveryMinutes: newDeliveryMinutes }
    }),

  incrementCompletedOrders: () =>
    set((state) => ({ completedOrders: state.completedOrders + 1 })),

  syncTelemetria: (telemetria: { rho_actual_mxn_h: number; ganancia_turno_mxn: number; pedidos_entregados: number }) =>
    set((state) => ({
      todayEarnings: telemetria.ganancia_turno_mxn,
      earningsPerHour: telemetria.rho_actual_mxn_h,
      completedOrders: telemetria.pedidos_entregados,
    })),

  addVygoGain: (gainMxn, kmSaved, minutesSaved) =>
    set((state) => ({
      vygoGainMxn: state.vygoGainMxn + gainMxn,
      vygoKmSaved: state.vygoKmSaved + kmSaved,
      vygoMinutesSaved: state.vygoMinutesSaved + minutesSaved,
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
