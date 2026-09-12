import type { Order, OrderStatus } from '@/types/order'
import { MOCK_ORDERS, NEW_ORDER_POOL } from './mock-data'
import { generateId } from '@/lib/utils'

export const ordersService = {
  getActiveOrders(): Order[] {
    return []
  },

  getCompletedOrders(): Order[] {
    return []
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
