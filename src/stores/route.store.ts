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
  buildRouteFromPlan: (orders: Order[], paradas: any[], geo?: RouteGeoJSON | null) => void
  advanceStop: () => void
  clearRoute: () => void
  setRouteGeoJSON: (geo: RouteGeoJSON | null) => void
}

export const useRouteStore = create<RouteStore>((set, get) => ({
  activeRoute: null,
  currentStopIndex: 0,
  routeGeoJSON: null,

  buildRouteFromPlan: (orders, paradas, geo) => {
    if (orders.length === 0) {
      set({ activeRoute: null, routeGeoJSON: null })
      return
    }

    if (!paradas || paradas.length === 0) {
      get().buildRoute(orders)
      if (geo) set({ routeGeoJSON: geo })
      return
    }

    const now = new Date()
    const stops = paradas.map((p, idx) => {
      const order = orders.find((o) => o.id === p.pedido_id) ?? orders[0]
      const isEntrega = p.tipo === 'entrega'
      const completed = isEntrega
        ? order.status === 'delivered'
        : (order.status === 'picked_up' || order.status === 'delivered')

      return {
        order,
        stopNumber: p.orden ?? (idx + 1),
        type: isEntrega ? ('dropoff' as const) : ('pickup' as const),
        completed,
        estimatedArrival: p.eta ? new Date(p.eta) : now,
      }
    })

    const totalDistance = orders.reduce((sum, o) => sum + o.distanceKm, 0)
    const totalEarnings = orders.reduce((sum, o) => sum + o.earnings, 0)
    const totalMinutes = orders.reduce((sum, o) => sum + o.estimatedMinutes, 0)

    const activeRoute: ActiveRoute = {
      stops,
      currentStopIndex: 0,
      totalDistanceKm: totalDistance,
      totalMinutes,
      totalEarnings,
      startedAt: now,
    }

    set({ activeRoute, currentStopIndex: 0, routeGeoJSON: geo ?? get().routeGeoJSON })
  },

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
