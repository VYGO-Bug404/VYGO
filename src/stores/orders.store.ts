import { create } from 'zustand'
import type { Order, OrderStatus } from '@/types/order'
import { ordersService } from '@/services/orders.service'
import { useDriverStore } from '@/stores/driver.store'

interface OrdersStore {
  activeOrders: Order[]
  completedOrders: Order[]
  pendingOffer: Order | null
  currentEarningsPerHour: number
  _nextRouteNumber: number

  acceptOffer: (order: Order) => void
  resetShift: () => void
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
  _nextRouteNumber: 4, // mocks already have 1, 2, 3

  setPendingOffer: (order) => set({ pendingOffer: order }),

  acceptOffer: (order) => {
    const { _nextRouteNumber } = get()
    const accepted: Order = {
      ...order,
      status: 'heading_to_pickup',
      acceptedAt: new Date(),
      routeNumber: order.routeNumber ?? _nextRouteNumber,
    }
    const projected = order.projectedEarningsPerHour ?? get().currentEarningsPerHour
    set((state) => ({
      activeOrders: [...state.activeOrders, accepted],
      pendingOffer: null,
      currentEarningsPerHour: projected,
      _nextRouteNumber: state._nextRouteNumber + 1,
    }))
    useDriverStore.getState().setStatus('active_route')
  },

  rejectOffer: () => set({ pendingOffer: null }),

  updateOrderStatus: (id, status) =>
    set((state) => {
      const updateList = (list: Order[]) =>
        list.map((o) => (o.id === id ? { ...o, status } : o))

      if (status === 'delivered') {
        const order = state.activeOrders.find((o) => o.id === id)
        const delivered = order ? { ...order, status: 'delivered' as const, deliveredAt: new Date() } : null
        const remaining = state.activeOrders.filter((o) => o.id !== id)
        if (remaining.length === 0) {
          useDriverStore.getState().setStatus('online')
        }
        return {
          activeOrders: remaining,
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

  resetShift: () =>
    set({
      activeOrders: [],
      pendingOffer: null,
      _nextRouteNumber: 1,
    }),

  simulateNewOrder: () => {
    const offer = ordersService.generateNewOffer()
    offer.currentEarningsPerHour = get().currentEarningsPerHour
    set({ pendingOffer: offer })
  },
}))
