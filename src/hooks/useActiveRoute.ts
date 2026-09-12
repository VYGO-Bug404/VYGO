import { useEffect } from 'react'
import { useOrdersStore } from '@/stores/orders.store'
import { useRouteStore } from '@/stores/route.store'

export function useActiveRoute() {
  const activeOrders = useOrdersStore((s) => s.activeOrders)
  const buildRoute = useRouteStore((s) => s.buildRoute)
  const activeRoute = useRouteStore((s) => s.activeRoute)
  const currentStopIndex = useRouteStore((s) => s.currentStopIndex)

  useEffect(() => {
    buildRoute(activeOrders)
  }, [activeOrders, buildRoute])

  const currentStop = activeRoute?.stops[currentStopIndex] ?? null
  const nextStop = activeRoute?.stops[currentStopIndex + 1] ?? null

  return {
    activeRoute,
    currentStop,
    nextStop,
    currentStopIndex,
    totalStops: activeRoute?.stops.length ?? 0,
  }
}
