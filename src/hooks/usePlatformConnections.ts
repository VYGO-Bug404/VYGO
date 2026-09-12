import { useState, useEffect, useCallback } from 'react'
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/stores/auth.store'

export type PlatformId = 'uber' | 'rappi' | 'didi'

export interface PlatformConnection {
  id: string
  platform: PlatformId
  driver_alias: string | null
  city: string | null
  connected_at: string
  is_active: boolean
}

export function usePlatformConnections() {
  const userId = useAuthStore((s) => s.userId)
  const [connections, setConnections] = useState<PlatformConnection[]>([])
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    if (!userId) { setLoading(false); return }
    const { data } = await supabase
      .from('platform_connections')
      .select('*')
      .eq('user_id', userId)
      .eq('is_active', true)
    setConnections((data as PlatformConnection[]) ?? [])
    setLoading(false)
  }, [userId])

  useEffect(() => { fetch() }, [fetch])

  const connect = async (platform: PlatformId, alias?: string, city?: string) => {
    if (!userId) return
    const { data, error } = await supabase
      .from('platform_connections')
      .upsert(
        { user_id: userId, platform, driver_alias: alias ?? null, city: city ?? null, is_active: true },
        { onConflict: 'user_id,platform' }
      )
      .select()
      .single()
    if (!error && data) {
      setConnections((prev) => {
        const filtered = prev.filter((c) => c.platform !== platform)
        return [...filtered, data as PlatformConnection]
      })
    }
    if (error) throw new Error(error.message)
  }

  const disconnect = async (platform: PlatformId) => {
    if (!userId) return
    const { error } = await supabase
      .from('platform_connections')
      .update({ is_active: false })
      .eq('user_id', userId)
      .eq('platform', platform)
    if (!error) {
      setConnections((prev) => prev.filter((c) => c.platform !== platform))
    }
    if (error) throw new Error(error.message)
  }

  const isConnected = (platform: PlatformId) =>
    connections.some((c) => c.platform === platform && c.is_active)

  const getConnection = (platform: PlatformId) =>
    connections.find((c) => c.platform === platform && c.is_active) ?? null

  return { connections, loading, connect, disconnect, isConnected, getConnection, refetch: fetch }
}
