import { useEffect, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/stores/auth.store'
import { useDriverStore } from '@/stores/driver.store'

const UPDATE_INTERVAL_MS = 8000   // Supabase update every 8s
const MIN_DISTANCE_M = 15         // Ignore updates < 15m of movement

function distanceMeters(lat1: number, lng1: number, lat2: number, lng2: number) {
  const R = 6371000
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLng = ((lng2 - lng1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
    Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export function useLocationTracking() {
  const userId = useAuthStore((s) => s.userId)
  const driverStatus = useDriverStore((s) => s.status)
  // For local/demo testing, allow tracking whenever geolocation is available
  const isActive = driverStatus !== 'offline'

  const lastSentRef = useRef<{ lat: number; lng: number; at: number } | null>(null)
  const pendingRef = useRef<GeolocationPosition | null>(null)
  const watchIdRef = useRef<number | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!isActive || !navigator.geolocation) return

    const DEMO_USER_ID = 'b9acb1bb-ee96-59c0-9e84-31f29368c97b'
    const targetUserId = (userId && userId !== 'driver-local') ? userId : DEMO_USER_ID

    const flush = async () => {
      const pos = pendingRef.current
      if (!pos) return

      const { latitude: lat, longitude: lng, heading, accuracy, speed } = pos.coords
      const now = Date.now()

      // Always keep localStorage fresh for immediate component reads
      try {
        localStorage.setItem('vygo-last-position', JSON.stringify({ lat, lng }))
      } catch {}

      const last = lastSentRef.current
      const movedEnough = !last || distanceMeters(last.lat, last.lng, lat, lng) >= MIN_DISTANCE_M
      const timeEnough = !last || now - last.at >= UPDATE_INTERVAL_MS

      if (!movedEnough && !timeEnough) return

      const { error } = await supabase
        .from('ubicaciones_conductores')
        .upsert(
          { user_id: targetUserId, lat, lng, heading, accuracy, speed, updated_at: new Date().toISOString() },
          { onConflict: 'user_id' }
        )

      if (!error) {
        lastSentRef.current = { lat, lng, at: now }
      }
    }

    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => { pendingRef.current = pos },
      () => {},
      { enableHighAccuracy: true, maximumAge: 3000, timeout: 10000 }
    )

    timerRef.current = setInterval(flush, UPDATE_INTERVAL_MS)

    return () => {
      if (watchIdRef.current !== null) navigator.geolocation.clearWatch(watchIdRef.current)
      if (timerRef.current !== null) clearInterval(timerRef.current)
    }
  }, [isActive, userId])
}
