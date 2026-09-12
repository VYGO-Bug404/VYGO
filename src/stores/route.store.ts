import { create } from 'zustand'
import type { ActiveRoute } from '@/types/route'
import type { Order } from '@/types/order'
import { routeService } from '@/services/route.service'

interface RouteStore {
  activeRoute: ActiveRoute | null
  currentStopIndex: number
  buildRoute: (orders: Order[]) => void
  advanceStop: () => void
  clearRoute: () => void
}

export const useRouteStore = create<RouteStore>((set, get) => ({
  activeRoute: null,
  currentStopIndex: 0,

  buildRoute: (orders) => {
    if (orders.length === 0) {
      set({ activeRoute: null })
      return
    }
    const route = routeService.buildRoute(orders)
    set({ activeRoute: route, currentStopIndex: 0 })
  },

  advanceStop: () => {
    const { activeRoute, currentStopIndex } = get()
    if (!activeRoute) return
    const next = currentStopIndex + 1
    if (next < activeRoute.stops.length) {
      set({ currentStopIndex: next })
    }
  },

  clearRoute: () => set({ activeRoute: null, currentStopIndex: 0 }),
}))
