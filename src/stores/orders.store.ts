import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Order, OrderStatus } from '@/types/order'
import { ordersService } from '@/services/orders.service'
import { useDriverStore } from '@/stores/driver.store'
import { useRouteStore } from '@/stores/route.store'
import { buildEarningsSummary, getTodayRange } from '@/lib/earningsAggregation'

// localStorage guarda JSON — las fechas vuelven como strings al rehidratar y hay que revivirlas
function reviveOrderDates(order: Order): Order {
  return {
    ...order,
    createdAt: new Date(order.createdAt),
    acceptedAt: order.acceptedAt ? new Date(order.acceptedAt) : undefined,
    deliveredAt: order.deliveredAt ? new Date(order.deliveredAt) : undefined,
    expiresAt: order.expiresAt ? new Date(order.expiresAt) : undefined,
  }
}

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

export const useOrdersStore = create<OrdersStore>()(
  persist(
    (set, get) => ({
      activeOrders: [],
      completedOrders: [],
      pendingOffer: null,
      _nextRouteNumber: 1,

      loadInitialData: async () => {
        const [completed] = await Promise.all([
          ordersService.fetchCompletedOrders(),
          ordersService.loadOfferPool(),
        ])
        // Merge en vez de sobreescribir: una entrega hecha en vivo (persistida localmente)
        // no debe desaparecer si todavía no llegó a Supabase.
        const existingIds = new Set(get().completedOrders.map((o) => o.id))
        const toAdd = completed.filter((o) => !existingIds.has(o.id))
        set({ completedOrders: [...get().completedOrders, ...toAdd] })
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

      updateOrderStatus: (id, status) => {
        set((state) => {
          const updateList = (list: Order[]) =>
            list.map((o) => (o.id === id ? { ...o, status } : o))

          if (status === 'delivered') {
            const order = state.activeOrders.find((o) => o.id === id)
            const delivered = order ? { ...order, status: 'delivered' as const, deliveredAt: new Date() } : null
            const remaining = state.activeOrders.filter((o) => o.id !== id)
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
        })

        if (status === 'delivered') {
          ordersService.markDelivered(id)
        }
      },

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
          offer.currentEarningsPerHour = buildEarningsSummary(get().completedOrders, getTodayRange()).perHour
          set({ pendingOffer: offer })
        } catch {
          console.warn('[orders] Pool vacío — no hay pedidos en la BD')
        }
      },
    }),
    {
      name: 'vygo-orders-completed',
      partialize: (state) => ({ completedOrders: state.completedOrders }),
      merge: (persisted, current) => {
        const p = persisted as { completedOrders?: Order[] } | undefined
        return {
          ...current,
          completedOrders: (p?.completedOrders ?? []).map(reviveOrderDates),
        }
      },
    }
  )
)
