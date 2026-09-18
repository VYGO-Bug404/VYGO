import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { DriverState, DriverStatus, Vehicle } from '@/types/driver'
import { driverService } from '@/services/driver.service'
import { useAuthStore } from '@/stores/auth.store'

interface DriverStore extends DriverState {
  vygoGainMxn: number
  vygoKmSaved: number
  vygoMinutesSaved: number
  vygoGainDate: string
  startShift: () => void
  endShift: () => void
  setStatus: (status: DriverStatus) => void
  setVehicle: (vehicle: Partial<Vehicle>) => void
  syncTelemetria: (t: { rho_actual_mxn_h: number; ganancia_turno_mxn: number; pedidos_entregados: number }) => void
  syncName: () => void
  addVygoGain: (gainMxn: number, kmSaved: number, minutesSaved: number) => void
}

function getSavedVehicle(): Partial<Vehicle> | null {
  try {
    const raw = localStorage.getItem('vygo-driver-vehicle')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function getInitialDriver() {
  const base = driverService.getDriver()
  const savedVehicle = getSavedVehicle()
  if (savedVehicle) {
    base.vehicle = { ...base.vehicle, ...savedVehicle }
  }
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

function todayKey() {
  return new Date().toISOString().slice(0, 10)
}

export const useDriverStore = create<DriverStore>()(
  persist(
    (set) => ({
      driver: getInitialDriver(),
      status: 'offline',
      shiftStartedAt: null,
      vygoGainMxn: 0,
      vygoKmSaved: 0,
      vygoMinutesSaved: 0,
      vygoGainDate: todayKey(),

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

      setVehicle: (vehicleData) =>
        set((state) => {
          const updatedVehicle = { ...state.driver.vehicle, ...vehicleData }
          try {
            localStorage.setItem('vygo-driver-vehicle', JSON.stringify(updatedVehicle))
          } catch {}
          return {
            driver: {
              ...state.driver,
              vehicle: updatedVehicle,
            },
          }
        }),

      // AGENT_URL no está configurado hoy — este callback es código muerto en la práctica.
      // Si en el futuro se conecta un backend de decisión real, esta telemetría debe
      // reconciliarse con los pedidos reales de orders.store, no sobreescribirlos.
      syncTelemetria: () => {},

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
    }),
    {
      name: 'vygo-driver-daily',
      partialize: (state) => ({
        vygoGainMxn: state.vygoGainMxn,
        vygoKmSaved: state.vygoKmSaved,
        vygoMinutesSaved: state.vygoMinutesSaved,
        vygoGainDate: state.vygoGainDate,
      }),
    }
  )
)

// Único reset del sistema: solo dispara cuando cambia el día calendario,
// nunca al iniciar/terminar una jornada.
if (useDriverStore.getState().vygoGainDate !== todayKey()) {
  useDriverStore.setState({ vygoGainMxn: 0, vygoKmSaved: 0, vygoMinutesSaved: 0, vygoGainDate: todayKey() })
}
