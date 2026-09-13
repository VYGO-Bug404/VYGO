import { create } from 'zustand'
import type { Order, OrderStatus } from '@/types/order'
import { ordersService } from '@/services/orders.service'
import { loadConfig, getConfig } from '@/services/config.service'
import { useDriverStore } from '@/stores/driver.store'
import { useRouteStore } from '@/stores/route.store'

interface OrdersStore {
  activeOrders: Order[]
  completedOrders: Order[]
  pendingOffer: Order | null
  _nextRouteNumber: number

  loadInitialData: () => Promise<void>
  acceptOffer: (order: Order, agentPlan?: any) => void
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
    await Promise.all([
      ordersService.loadOfferPool(),
      loadConfig(),
    ])
    // No pre-cargamos pedidos de Supabase como métricas del usuario:
    // los pedidos 'entregado' en la BD son datos de demostración, no del usuario actual.
    // El driver store arranca en 0 y se alimenta solo de entregas reales de la sesión.
  },

  setPendingOffer: (order) => set({ pendingOffer: order }),

  acceptOffer: (order, agentPlan) => {
    const { _nextRouteNumber, activeOrders } = get()
    if (activeOrders.length >= getConfig().maxPedidosSimultaneos) return
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
    // Build route from updated active orders using agent sequence if available
    const updated = [...get().activeOrders]
    if (agentPlan?.paradas && agentPlan.paradas.length > 0) {
      useRouteStore.getState().buildRouteFromPlan(updated, agentPlan.paradas, agentPlan.geometria)
    } else {
      useRouteStore.getState().buildRoute(updated)
    }
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
