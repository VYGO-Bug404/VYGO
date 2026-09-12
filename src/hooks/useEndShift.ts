import { useState } from 'react'
import { useDriverStore } from '@/stores/driver.store'
import { useOrdersStore } from '@/stores/orders.store'

export function useEndShift() {
  const [confirming, setConfirming] = useState(false)
  const endShift = useDriverStore((s) => s.endShift)
  const resetShift = useOrdersStore((s) => s.resetShift)
  const activeOrders = useOrdersStore((s) => s.activeOrders)

  const tryEndShift = () => {
    if (activeOrders.length > 0) {
      setConfirming(true)
    } else {
      endShift()
      resetShift()
    }
  }

  const confirmEnd = () => {
    endShift()
    resetShift()
    setConfirming(false)
  }

  const cancelConfirm = () => setConfirming(false)

  return { tryEndShift, confirming, confirmEnd, cancelConfirm, activeOrders }
}
