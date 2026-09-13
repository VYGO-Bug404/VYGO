import { create } from 'zustand'
import type { Order, OrderStatus } from '@/types/order'
import { ordersService } from '@/services/orders.service'
import { useDriverStore } from '@/stores/driver.store'
import { useRouteStore } from '@/stores/route.store'

interface OrdersStore {
  activeOrders: Order[]
  completedOrders: Order[]
  pendingOffer: Order | null
  _nextRouteNumber: number

  loadInitialData: () => Promise<void>
  acceptOffer: (order: Order) => void
  resetShift: () => void
  rejectOffer: () => void
  setPendingOffer: (order: Order) => void
  updateOrderStatus: (id: string, status: OrderStatus) => void
  simulateNewOrder: () => void
  advanceOrder: (id: string) => void
}

export const useOrdersStore = create<OrdersStore>((set, get) => ({
  activeOrders: [],
  completedOrders: [],
  pendingOffer: null,
  _nextRouteNumber: 1,

  loadInitialData: async () => {
    const [completed] = await Promise.all([
      ordersService.fetchCompletedOrders(),
      ordersService.loadOfferPool(),
    ])
    set({ completedOrders: completed })
  },

  setPendingOffer: (order) => set({ pendingOffer: order }),

  acceptOffer: (order) => {
    const { _nextRouteNumber } = get()
    const accepted: Order = {
      ...order,
      status: 'heading_to_pickup',
      acceptedAt: new Date(),
      routeNumber: order.routeNumber ?? _nextRouteNumber,
    }
    set((state) => ({
      activeOrders: [...state.activeOrders, accepted],
      pendingOffer: null,
      _nextRouteNumber: state._nextRouteNumber + 1,
    }))
    useDriverStore.getState().setStatus('active_route')
    // Build route from updated active orders
    const updated = [...get().activeOrders]
    useRouteStore.getState().buildRoute(updated)
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
        if (order) {
          useDriverStore.getState().addEarnings(order.earnings, order.estimatedMinutes)
          useDriverStore.getState().incrementCompletedOrders()
        }
        if (remaining.length === 0) {
          useDriverStore.getState().setStatus('online')
          useRouteStore.getState().clearRoute()
        } else {
          useRouteStore.getState().buildRoute(remaining)
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
    if (next) get().updateOrderStatus(id, next)
  },

  resetShift: () => {
    set({ activeOrders: [], pendingOffer: null, _nextRouteNumber: 1 })
    useRouteStore.getState().clearRoute()
  },

  simulateNewOrder: () => {
    try {
      const offer = ordersService.generateNewOffer()
      offer.currentEarningsPerHour = useDriverStore.getState().earningsPerHour
      set({ pendingOffer: offer })
    } catch {
      console.warn('[orders] Pool vacío — no hay pedidos en la BD')
    }
  },
}))
