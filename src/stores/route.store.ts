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

    // If OSRM geometry already set (≥20 coords = real streets), keep it.
    // Only re-fetch when the route changes after delivering an order.
    const existing = get().routeGeoJSON
    if (existing && existing.coordinates.length >= 20) {
      set({ activeRoute: route, currentStopIndex: 0 })
      return
    }

    // No valid geometry yet — fetch OSRM for remaining stops (no driver pos)
    const waypoints: [number, number][] = orders.flatMap((o): [number, number][] => {
      const pts: [number, number][] = []
      if (o.status !== 'picked_up') pts.push([o.pickup.lng, o.pickup.lat])
      pts.push([o.dropoff.lng, o.dropoff.lat])
      return pts
    })

    set({ activeRoute: route, currentStopIndex: 0 })
    fetchStreetRoute(waypoints).then((geo) => {
      set({ routeGeoJSON: geo ?? (waypoints.length >= 2 ? { type: 'LineString', coordinates: waypoints } : null) })
    })
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
