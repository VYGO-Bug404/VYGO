export type Platform = 'uber' | 'rappi' | 'didi'

export type OrderStatus =
  | 'offered'
  | 'accepted'
  | 'heading_to_pickup'
  | 'picked_up'
  | 'delivered'
  | 'cancelled'

export type Recommendation = 'excellent' | 'good' | 'neutral' | 'bad'

export interface Location {
  name?: string
  address: string
  neighborhood: string
  lat: number
  lng: number
}

export interface Order {
  id: string
  orderNumber: string
  platform: Platform
  restaurantName: string
  earnings: number
  pickup: Location
  dropoff: Location
  distanceKm: number
  estimatedMinutes: number
  extraDistanceKm?: number
  extraMinutes?: number
  currentEarningsPerHour?: number
  projectedEarningsPerHour?: number
  earningsPerKm?: number
  recommendation?: Recommendation
  status: OrderStatus
  createdAt: Date
  acceptedAt?: Date
  deliveredAt?: Date
}
