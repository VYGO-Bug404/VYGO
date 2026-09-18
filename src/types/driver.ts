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
  year?: string
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
  shiftStartedAt: Date | null
}
