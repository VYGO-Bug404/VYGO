import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthStore {
  isAuthenticated: boolean
  email: string | null
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      email: null,

      login: async (email, _password) => {
        // Mock: any credentials work
        await new Promise((r) => setTimeout(r, 900))
        set({ isAuthenticated: true, email })
      },

      register: async (_name, email, _password) => {
        await new Promise((r) => setTimeout(r, 1000))
        set({ isAuthenticated: true, email })
      },

      logout: () => set({ isAuthenticated: false, email: null }),
    }),
    { name: 'vygo-auth' }
  )
)
