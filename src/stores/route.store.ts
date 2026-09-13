import { create } from 'zustand'
import type { ActiveRoute } from '@/types/route'
import type { Order } from '@/types/order'
import { routeService } from '@/services/route.service'

type RouteGeoJSON = { type: 'LineString'; coordinates: [number, number][] }

interface RouteStore {
  activeRoute: ActiveRoute | null
  currentStopIndex: number
  routeGeoJSON: RouteGeoJSON | null
  buildRoute: (orders: Order[]) => void
  advanceStop: () => void
  clearRoute: () => void
  setRouteGeoJSON: (geo: RouteGeoJSON | null) => void
}

export const useRouteStore = create<RouteStore>((set, get) => ({
  activeRoute: null,
  currentStopIndex: 0,
  routeGeoJSON: null,

  buildRoute: (orders) => {
    if (orders.length === 0) {
      set({ activeRoute: null, routeGeoJSON: null })
      return
    }
    const route = routeService.buildRoute(orders)
    // Keep existing geometry from agent; only build straight-line fallback if missing
    const existing = get().routeGeoJSON
    if (!existing || existing.coordinates.length < 2) {
      const coords: [number, number][] = []
      try {
        const raw = localStorage.getItem('vygo-last-position')
        if (raw) {
          const p = JSON.parse(raw)
          if (typeof p.lng === 'number' && typeof p.lat === 'number') coords.push([p.lng, p.lat])
        }
      } catch {}
      orders.forEach((o) => {
        if (o.status !== 'picked_up') coords.push([o.pickup.lng, o.pickup.lat])
        coords.push([o.dropoff.lng, o.dropoff.lat])
      })
      set({ activeRoute: route, currentStopIndex: 0, routeGeoJSON: coords.length >= 2 ? { type: 'LineString', coordinates: coords } : null })
    } else {
      set({ activeRoute: route, currentStopIndex: 0 })
    }
  },

  advanceStop: () => {
    const { activeRoute, currentStopIndex } = get()
    if (!activeRoute) return
    const next = currentStopIndex + 1
    if (next < activeRoute.stops.length) {
      set({ currentStopIndex: next })
    }
  },

  clearRoute: () => set({ activeRoute: null, currentStopIndex: 0, routeGeoJSON: null }),

  setRouteGeoJSON: (geo) => set({ routeGeoJSON: geo }),
}))
