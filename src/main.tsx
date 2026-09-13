import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import { setWorkerUrl } from 'maplibre-gl'
import MaplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { App } from './App'

setWorkerUrl(MaplibreWorkerUrl)
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/stores/auth.store'
import { useDriverStore } from '@/stores/driver.store'
import { useOrdersStore } from '@/stores/orders.store'

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

// Sync Supabase auth state changes (e.g. token refresh, sign-out from another tab)
supabase.auth.onAuthStateChange((event, session) => {
  if ((event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED' || event === 'USER_UPDATED') && session) {
    const meta = session.user.user_metadata
    useAuthStore.setState({
      isAuthenticated: true,
      email: session.user.email ?? null,
      phone: session.user.phone ?? null,
      userId: session.user.id,
      fullName: meta?.full_name ?? meta?.name ?? null,
    })
    useDriverStore.getState().syncName()
  } else if (event === 'SIGNED_OUT') {
    useAuthStore.setState({ isAuthenticated: false, email: null, phone: null, userId: null, fullName: null })
  }
})

// Restore existing session on page load
useAuthStore.getState().initSession().then(() => {
  useDriverStore.getState().syncName()
  useOrdersStore.getState().loadInitialData()
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>
  )
})
