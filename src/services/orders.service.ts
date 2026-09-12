import type { Order, OrderStatus } from '@/types/order'
import { MOCK_ORDERS, NEW_ORDER_POOL } from './mock-data'
import { generateId } from '@/lib/utils'

export const ordersService = {
  getActiveOrders(): Order[] {
    return MOCK_ORDERS.filter((o) =>
      ['heading_to_pickup', 'picked_up', 'accepted'].includes(o.status)
    )
  },

  getCompletedOrders(): Order[] {
    return MOCK_ORDERS.filter((o) => o.status === 'delivered')
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
    }
  },

  updateStatus(order: Order, status: OrderStatus): Order {
    return { ...order, status }
  },
}
