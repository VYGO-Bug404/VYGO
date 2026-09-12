import type { Order } from './order'

export interface RouteStop {
  order: Order
  stopNumber: number
  type: 'pickup' | 'dropoff'
  completed: boolean
  estimatedArrival: Date
}

export interface ActiveRoute {
  stops: RouteStop[]
  currentStopIndex: number
  totalDistanceKm: number
  totalMinutes: number
  totalEarnings: number
  startedAt: Date
}

export interface NavigationBanner {
  distance: string
  streetName: string
  direction: 'left' | 'right' | 'straight'
}
