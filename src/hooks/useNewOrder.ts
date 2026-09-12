import { useEffect } from 'react'
import { useOrdersStore } from '@/stores/orders.store'
import { useDriverStore } from '@/stores/driver.store'

export function useNewOrder() {
  const simulateNewOrder = useOrdersStore((s) => s.simulateNewOrder)
  const pendingOffer = useOrdersStore((s) => s.pendingOffer)
  const driverStatus = useDriverStore((s) => s.status)

  // Vibrate when a new offer arrives
  useEffect(() => {
    if (!pendingOffer) return
    if (navigator.vibrate) navigator.vibrate([200, 100, 200])
  }, [pendingOffer?.id])

  useEffect(() => {
    if (driverStatus === 'offline') return

    const interval = setInterval(() => {
      if (!pendingOffer) simulateNewOrder()
    }, 20000)

    return () => clearInterval(interval)
  }, [driverStatus, pendingOffer, simulateNewOrder])
}
