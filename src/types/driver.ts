export type DriverStatus =
  | 'offline'
  | 'online'
  | 'active_route'
  | 'heading_to_pickup'
  | 'pickup'
  | 'delivery'
  | 'completed'

export interface Vehicle {
  type: 'moto' | 'car' | 'bicycle'
  brand: string
  model: string
}

export interface Driver {
  id: string
  name: string
  avatarInitials: string
  vehicle: Vehicle
  platforms: string[]
  rating: number
  totalDeliveries: number
  memberSince: string
}

export interface DriverState {
  driver: Driver
  status: DriverStatus
  todayEarnings: number
  earningsPerHour: number
  completedOrders: number
  shiftStartedAt: Date | null
}
