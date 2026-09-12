import type { Order } from '@/types/order'
import type { ActiveRoute, RouteStop } from '@/types/route'
import { addMinutes } from '@/lib/utils'

export const routeService = {
  buildRoute(orders: Order[]): ActiveRoute {
    const now = new Date()
    let runningMinutes = 0
    let totalEarnings = 0
    let totalDistance = 0

    const stops: RouteStop[] = []

    orders.forEach((order, idx) => {
      runningMinutes += Math.round(order.estimatedMinutes / 2)
      stops.push({
        order,
        stopNumber: idx + 1,
        type: 'pickup',
        completed: order.status === 'picked_up' || order.status === 'delivered',
        estimatedArrival: addMinutes(now, runningMinutes),
      })

      runningMinutes += Math.round(order.estimatedMinutes / 2)
      stops.push({
        order,
        stopNumber: idx + 1,
        type: 'dropoff',
        completed: order.status === 'delivered',
        estimatedArrival: addMinutes(now, runningMinutes),
      })

      totalEarnings += order.earnings
      totalDistance += order.distanceKm
    })

    return {
      stops,
      currentStopIndex: 0,
      totalDistanceKm: totalDistance,
      totalMinutes: runningMinutes,
      totalEarnings,
      startedAt: now,
    }
  },

  getNavigationInstruction(stopIndex: number): { distance: string; streetName: string } {
    const instructions = [
      { distance: '250 m', streetName: 'Av. Hidalgo' },
      { distance: '1.2 km', streetName: 'Av. Constitución' },
      { distance: '800 m', streetName: 'Av. Vasconcelos' },
      { distance: '500 m', streetName: 'Av. Garza Sada' },
    ]
    return instructions[stopIndex % instructions.length]
  },
}
