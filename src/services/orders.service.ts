import type { Order, OrderStatus, Platform, Recommendation } from '@/types/order'
import { supabase } from '@/lib/supabase'

const ZONA_LABEL: Record<string, string> = {
  centro: 'Centro',
  san_pedro: 'San Pedro',
  tec: 'Tecnológico',
  cumbres: 'Cumbres',
  obispado: 'Obispado',
  guadalupe: 'Guadalupe',
  santa_catarina: 'Santa Catarina',
}

function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLng = ((lng2 - lng1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2
  return R * 2 * Math.asin(Math.sqrt(a))
}

function toRecommendation(epk: number): Recommendation {
  if (epk >= 25) return 'excellent'
  if (epk >= 18) return 'good'
  if (epk >= 12) return 'neutral'
  return 'bad'
}

function toStatus(estado: string): OrderStatus {
  const map: Record<string, OrderStatus> = {
    creado: 'offered',
    buscando: 'offered',
    asignado: 'accepted',
    en_camino: 'heading_to_pickup',
    entregado: 'delivered',
    cancelado: 'cancelled',
  }
  return map[estado] ?? 'offered'
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapRow(row: any): Order {
  const distanceKm = parseFloat(
    haversineKm(row.origen_lat, row.origen_lng, row.destino_lat, row.destino_lng).toFixed(1)
  )
  const earnings = parseFloat(row.precio)
  const earningsPerKm = parseFloat((earnings / Math.max(distanceKm, 0.1)).toFixed(2))
  const estimatedMinutes = Math.round(distanceKm * 3.5 + 2)
  const zona: string = row.contexto?.zona ?? ''
  const neighborhood = ZONA_LABEL[zona] ?? zona

  return {
    id: row.id,
    orderNumber: row.id_externo ?? row.id.slice(0, 6).toUpperCase(),
    platform: (row.plataforma as Platform) ?? 'uber',
    restaurantName: row.contexto?.comercio_nombre ?? row.origen_direccion,
    earnings,
    pickup: {
      name: row.contexto?.comercio_nombre,
      address: row.origen_direccion,
      neighborhood,
      lat: row.origen_lat,
      lng: row.origen_lng,
    },
    dropoff: {
      address: row.destino_direccion,
      neighborhood,
      lat: row.destino_lat,
      lng: row.destino_lng,
    },
    distanceKm,
    estimatedMinutes,
    earningsPerKm,
    recommendation: toRecommendation(earningsPerKm),
    status: toStatus(row.estado),
    createdAt: new Date(row.creado_en),
    acceptedAt: row.aceptado_en ? new Date(row.aceptado_en) : undefined,
    deliveredAt: row.entregado_en ? new Date(row.entregado_en) : undefined,
  }
}

let _offerPool: Order[] = []

export const ordersService = {
  getActiveOrders(): Order[] {
    return []
  },

  getCompletedOrders(): Order[] {
    return []
  },

  async fetchCompletedOrders(): Promise<Order[]> {
    const todayStart = new Date()
    todayStart.setHours(0, 0, 0, 0)

    const { data, error } = await supabase
      .from('pedidos_vista')
      .select('*')
      .eq('estado', 'entregado')
      .gte('entregado_en', todayStart.toISOString())
      .order('entregado_en', { ascending: false })
      .limit(50)
    if (error) {
      console.error('fetchCompletedOrders:', error)
      return []
    }
    return (data ?? []).map(mapRow)
  },

  async loadOfferPool(): Promise<void> {
    const { data, error } = await supabase
      .from('pedidos_vista')
      .select('*')
      .eq('estado', 'buscando')
    if (error) {
      console.error('loadOfferPool:', error)
      return
    }
    _offerPool = (data ?? []).map(mapRow)
  },

  generateNewOffer(): Order {
    const pool = _offerPool.length > 0 ? _offerPool : []
    if (pool.length === 0) {
      throw new Error('Offer pool not loaded yet')
    }
    const template = pool[Math.floor(Math.random() * pool.length)]
    return {
      ...template,
      id: `offer-${Date.now()}`,
      status: 'offered',
      createdAt: new Date(),
      expiresAt: new Date(Date.now() + 30_000),
    }
  },

  updateStatus(order: Order, status: OrderStatus): Order {
    return { ...order, status }
  },
}
