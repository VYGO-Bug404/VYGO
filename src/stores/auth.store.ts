import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { supabase } from '@/lib/supabase'

interface AuthStore {
  isAuthenticated: boolean
  email: string | null
  userId: string | null
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  initSession: () => Promise<void>
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      email: null,
      userId: null,

      login: async (email, password) => {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw new Error(error.message)
        set({ isAuthenticated: true, email: data.user.email ?? email, userId: data.user.id })
      },

      register: async (name, email, password) => {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: name } },
        })
        if (error) throw new Error(error.message)
        // If email confirmation is disabled, session is available immediately
        if (data.session) {
          set({ isAuthenticated: true, email: data.user?.email ?? email, userId: data.user?.id ?? null })
        } else {
          // Email confirmation required — still log in locally so UX flows
          set({ isAuthenticated: true, email, userId: data.user?.id ?? null })
        }
      },

      logout: async () => {
        await supabase.auth.signOut()
        set({ isAuthenticated: false, email: null, userId: null })
      },

      initSession: async () => {
        const { data } = await supabase.auth.getSession()
        if (data.session) {
          set({
            isAuthenticated: true,
            email: data.session.user.email ?? null,
            userId: data.session.user.id,
          })
        }
      },
    }),
    { name: 'vygo-auth' }
  )
)
