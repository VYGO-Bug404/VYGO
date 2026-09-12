import { create } from 'zustand'
import type { Order, OrderStatus } from '@/types/order'
import { ordersService } from '@/services/orders.service'

interface OrdersStore {
  activeOrders: Order[]
  completedOrders: Order[]
  pendingOffer: Order | null
  currentEarningsPerHour: number

  acceptOffer: (order: Order) => void
  rejectOffer: () => void
  setPendingOffer: (order: Order) => void
  updateOrderStatus: (id: string, status: OrderStatus) => void
  simulateNewOrder: () => void
  advanceOrder: (id: string) => void
}

export const useOrdersStore = create<OrdersStore>((set, get) => ({
  activeOrders: ordersService.getActiveOrders(),
  completedOrders: ordersService.getCompletedOrders(),
  pendingOffer: null,
  currentEarningsPerHour: 192,

  setPendingOffer: (order) => set({ pendingOffer: order }),

  acceptOffer: (order) => {
    const accepted: Order = { ...order, status: 'heading_to_pickup', acceptedAt: new Date() }
    const projected = order.projectedEarningsPerHour ?? get().currentEarningsPerHour
    set((state) => ({
      activeOrders: [...state.activeOrders, accepted],
      pendingOffer: null,
      currentEarningsPerHour: projected,
    }))
  },

  rejectOffer: () => set({ pendingOffer: null }),

  updateOrderStatus: (id, status) =>
    set((state) => {
      const updateList = (list: Order[]) =>
        list.map((o) => (o.id === id ? { ...o, status } : o))

      if (status === 'delivered') {
        const order = state.activeOrders.find((o) => o.id === id)
        const delivered = order ? { ...order, status: 'delivered' as const, deliveredAt: new Date() } : null
        return {
          activeOrders: state.activeOrders.filter((o) => o.id !== id),
          completedOrders: delivered
            ? [...state.completedOrders, delivered]
            : state.completedOrders,
        }
      }

      return { activeOrders: updateList(state.activeOrders) }
    }),

  advanceOrder: (id) => {
    const { activeOrders } = get()
    const order = activeOrders.find((o) => o.id === id)
    if (!order) return

    const nextStatus: Record<string, OrderStatus> = {
      heading_to_pickup: 'picked_up',
      accepted: 'picked_up',
      picked_up: 'delivered',
    }

    const next = nextStatus[order.status]
    if (next) {
      get().updateOrderStatus(id, next)
    }
  },

  simulateNewOrder: () => {
    const offer = ordersService.generateNewOffer()
    offer.currentEarningsPerHour = get().currentEarningsPerHour
    set({ pendingOffer: offer })
  },
}))
