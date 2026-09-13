import type { Order, OrderStatus } from '@/types/order'
import { MOCK_ORDERS, NEW_ORDER_POOL } from './mock-data'
import { generateId } from '@/lib/utils'

export const ordersService = {
  getActiveOrders(): Order[] {
    return []
  },

  getCompletedOrders(): Order[] {
    // Historial de demo — pedidos completados esta sesión para mostrar en /orders
    const now = Date.now()
    return [
      {
        id: 'hist-1', orderNumber: '4012', platform: 'rappi',
        restaurantName: 'Sushi Roll Macroplaza',
        earnings: 62, distanceKm: 2.1, estimatedMinutes: 9,
        earningsPerKm: 29.5, recommendation: 'good',
        pickup: { name: 'Sushi Roll Macroplaza', address: 'Macroplaza, Centro', neighborhood: 'Centro', lat: 25.6698, lng: -100.3102 },
        dropoff: { address: 'Av. Constitución 1800', neighborhood: 'Centro', lat: 25.6720, lng: -100.3080 },
        status: 'delivered', createdAt: new Date(now - 180 * 60000), acceptedAt: new Date(now - 178 * 60000), deliveredAt: new Date(now - 170 * 60000),
      },
      {
        id: 'hist-2', orderNumber: '3871', platform: 'uber',
        restaurantName: 'Centrito Burgers',
        earnings: 66, distanceKm: 2.4, estimatedMinutes: 10,
        earningsPerKm: 27.5, recommendation: 'excellent',
        pickup: { name: 'Centrito Burgers', address: 'Av. Vasconcelos 300', neighborhood: 'San Pedro', lat: 25.6580, lng: -100.3640 },
        dropoff: { address: 'Calz. del Valle 440', neighborhood: 'San Pedro', lat: 25.6610, lng: -100.3600 },
        status: 'delivered', createdAt: new Date(now - 140 * 60000), acceptedAt: new Date(now - 138 * 60000), deliveredAt: new Date(now - 129 * 60000),
      },
      {
        id: 'hist-3', orderNumber: '5502', platform: 'didi',
        restaurantName: 'Chilaquiles Tec',
        earnings: 58, distanceKm: 1.8, estimatedMinutes: 8,
        earningsPerKm: 32.2, recommendation: 'good',
        pickup: { name: 'Chilaquiles Tec', address: 'Av. Garza Sada 2101', neighborhood: 'Tecnológico', lat: 25.6515, lng: -100.2895 },
        dropoff: { address: 'Calle del Roble 300', neighborhood: 'Tecnológico', lat: 25.6540, lng: -100.2920 },
        status: 'delivered', createdAt: new Date(now - 100 * 60000), acceptedAt: new Date(now - 98 * 60000), deliveredAt: new Date(now - 91 * 60000),
      },
      {
        id: 'hist-4', orderNumber: '6193', platform: 'rappi',
        restaurantName: 'Tacos El Primo',
        earnings: 57, distanceKm: 1.9, estimatedMinutes: 9,
        earningsPerKm: 30.0, recommendation: 'good',
        pickup: { name: 'Tacos El Primo', address: 'Av. Cuauhtémoc 400', neighborhood: 'Centro', lat: 25.6740, lng: -100.3160 },
        dropoff: { address: 'Av. Colón 720', neighborhood: 'Centro', lat: 25.6760, lng: -100.3120 },
        status: 'delivered', createdAt: new Date(now - 60 * 60000), acceptedAt: new Date(now - 58 * 60000), deliveredAt: new Date(now - 50 * 60000),
      },
      {
        id: 'hist-5', orderNumber: '7744', platform: 'uber',
        restaurantName: 'Pangea Express Valle Oriente',
        earnings: 74, distanceKm: 3.2, estimatedMinutes: 12,
        earningsPerKm: 23.1, recommendation: 'excellent',
        pickup: { name: 'Pangea Express', address: 'Av. David Alfaro Siqueiros 106', neighborhood: 'San Pedro', lat: 25.6420, lng: -100.3310 },
        dropoff: { address: 'Av. Insurgentes 1540', neighborhood: 'San Pedro', lat: 25.6580, lng: -100.3440 },
        status: 'delivered', createdAt: new Date(now - 25 * 60000), acceptedAt: new Date(now - 23 * 60000), deliveredAt: new Date(now - 12 * 60000),
      },
    ] as Order[]
  },

  getOrderById(id: string): Order | undefined {
    return MOCK_ORDERS.find((o) => o.id === id)
  },

  generateNewOffer(): Order {
    const pool = NEW_ORDER_POOL
    const template = pool[Math.floor(Math.random() * pool.length)]
    return {
      ...template,
      id: `order-${generateId()}`,
      status: 'offered',
      createdAt: new Date(),
      expiresAt: new Date(Date.now() + 30_000), // 30s to decide
    }
  },

  updateStatus(order: Order, status: OrderStatus): Order {
    return { ...order, status }
  },
}
