import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import { App } from './App'
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/stores/auth.store'

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

// Sync Supabase auth state changes (e.g. token refresh, sign-out from another tab)
supabase.auth.onAuthStateChange((event, session) => {
  const store = useAuthStore.getState()
  if (event === 'SIGNED_IN' && session) {
    useAuthStore.setState({
      isAuthenticated: true,
      email: session.user.email ?? null,
      userId: session.user.id,
    })
  } else if (event === 'SIGNED_OUT') {
    useAuthStore.setState({ isAuthenticated: false, email: null, userId: null })
  }
})

// Restore existing session on page load
useAuthStore.getState().initSession().then(() => {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>
  )
})
