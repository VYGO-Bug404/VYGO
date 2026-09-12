import { useEffect, useRef, useState } from 'react'

export function useCountUp(target: number, duration = 600): number {
  const [current, setCurrent] = useState(target)
  const prevTarget = useRef(target)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    if (prevTarget.current === target) return

    const start = prevTarget.current
    const diff = target - start
    const startTime = performance.now()

    const animate = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setCurrent(Math.round(start + diff * eased))

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate)
      } else {
        prevTarget.current = target
      }
    }

    rafRef.current = requestAnimationFrame(animate)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [target, duration])

  return current
}
