import { useState, useEffect, useRef } from 'react'

export function useCountUp(target: number, duration = 700): number {
  const [value, setValue] = useState(target)
  const prevRef = useRef(target)

  useEffect(() => {
    if (prevRef.current === target) return
    const start = prevRef.current
    const diff = target - start
    const startTime = performance.now()

    const tick = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
      setValue(Math.round(start + diff * eased))
      if (progress < 1) requestAnimationFrame(tick)
      else prevRef.current = target
    }

    requestAnimationFrame(tick)
  }, [target, duration])

  return value
}
