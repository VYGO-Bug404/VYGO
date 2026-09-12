import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { supabase } from '@/lib/supabase'

interface AuthStore {
  isAuthenticated: boolean
  email: string | null
  phone: string | null
  userId: string | null
  fullName: string | null
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  signInWithApple: () => Promise<void>
  signInWithGoogle: () => Promise<void>
  signInWithPhone: (phone: string) => Promise<void>
  verifyPhoneOtp: (phone: string, token: string) => Promise<void>
  logout: () => Promise<void>
  initSession: () => Promise<void>
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      email: null,
      phone: null,
      userId: null,
      fullName: null,

      login: async (email, password) => {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw new Error(error.message)
        const name = data.user.user_metadata?.full_name ?? null
        set({ isAuthenticated: true, email: data.user.email ?? email, userId: data.user.id, fullName: name })
      },

      register: async (name, email, password) => {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: name } },
        })
        if (error) throw new Error(error.message)
        if (data.session) {
          set({ isAuthenticated: true, email: data.user?.email ?? email, userId: data.user?.id ?? null, fullName: name })
        } else {
          set({ isAuthenticated: true, email, userId: data.user?.id ?? null, fullName: name })
        }
      },

      signInWithApple: async () => {
        const { error } = await supabase.auth.signInWithOAuth({
          provider: 'apple',
          options: { redirectTo: `${window.location.origin}/` },
        })
        if (error) throw new Error(error.message)
      },

      signInWithGoogle: async () => {
        const { error } = await supabase.auth.signInWithOAuth({
          provider: 'google',
          options: { redirectTo: `${window.location.origin}/` },
        })
        if (error) throw new Error(error.message)
      },

      signInWithPhone: async (phone: string) => {
        const { error } = await supabase.auth.signInWithOtp({ phone })
        if (error) throw new Error(error.message)
      },

      verifyPhoneOtp: async (phone: string, token: string) => {
        const { data, error } = await supabase.auth.verifyOtp({ phone, token, type: 'sms' })
        if (error) throw new Error(error.message)
        if (data.session) {
          set({
            isAuthenticated: true,
            phone: data.session.user.phone ?? phone,
            userId: data.session.user.id,
          })
        }
      },

      logout: async () => {
        await supabase.auth.signOut()
        set({ isAuthenticated: false, email: null, phone: null, userId: null, fullName: null })
      },

      initSession: async () => {
        const { data } = await supabase.auth.getSession()
        if (data.session) {
          const meta = data.session.user.user_metadata
          set({
            isAuthenticated: true,
            email: data.session.user.email ?? null,
            phone: data.session.user.phone ?? null,
            userId: data.session.user.id,
            fullName: meta?.full_name ?? meta?.name ?? null,
          })
        } else {
          set({ isAuthenticated: false, email: null, phone: null, userId: null, fullName: null })
        }
      },
    }),
    { name: 'vygo-auth' }
  )
)
