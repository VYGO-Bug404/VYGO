import { create } from 'zustand'
import type { ActiveRoute } from '@/types/route'
import type { Order } from '@/types/order'
import { routeService } from '@/services/route.service'
import { fetchStreetRoute } from '@/services/routing.service'

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

function getDriverPos(): [number, number] {
  try {
    const raw = localStorage.getItem('vygo-last-position')
    if (raw) {
      const p = JSON.parse(raw)
      if (typeof p.lng === 'number' && typeof p.lat === 'number') return [p.lng, p.lat]
    }
  } catch {}
  return [-100.3094, 25.6714]
}

function ordersToWaypoints(orders: Order[]): [number, number][] {
  const pts: [number, number][] = [getDriverPos()]
  orders.forEach((o) => {
    if (o.status !== 'picked_up') pts.push([o.pickup.lng, o.pickup.lat])
    pts.push([o.dropoff.lng, o.dropoff.lat])
  })
  return pts
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
    set({ activeRoute: route, currentStopIndex: 0 })

    // If we already have geometry from backend, keep it; otherwise fetch street route
    const existing = get().routeGeoJSON
    if (!existing || existing.coordinates.length < 2) {
      const waypoints = ordersToWaypoints(orders)
      fetchStreetRoute(waypoints).then((geo) => {
        set({ routeGeoJSON: geo ?? { type: 'LineString', coordinates: waypoints } })
      })
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
