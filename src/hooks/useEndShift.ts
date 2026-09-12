import { useState, useRef } from 'react'
import { useDriverStore } from '@/stores/driver.store'
import { useOrdersStore } from '@/stores/orders.store'

export function useEndShift() {
  const [confirming, setConfirming] = useState(false)
  const onEndRef = useRef<(() => void) | undefined>(undefined)
  const endShift = useDriverStore((s) => s.endShift)
  const resetShift = useOrdersStore((s) => s.resetShift)
  const activeOrders = useOrdersStore((s) => s.activeOrders)

  const tryEndShift = (onEnd?: () => void) => {
    onEndRef.current = onEnd
    if (activeOrders.length > 0) {
      setConfirming(true)
    } else {
      endShift()
      resetShift()
      onEnd?.()
    }
  }

  const confirmEnd = () => {
    endShift()
    resetShift()
    setConfirming(false)
    onEndRef.current?.()
  }

  const cancelConfirm = () => setConfirming(false)

  return { tryEndShift, confirming, confirmEnd, cancelConfirm, activeOrders }
}
