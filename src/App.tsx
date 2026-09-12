import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from '@/components/layout/AppLayout'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { useAuthStore } from '@/stores/auth.store'
import { LoginPage } from '@/pages/Login'
import { RegisterPage } from '@/pages/Register'
import { HomePage } from '@/pages/Home'
import { OrdersPage } from '@/pages/Orders'
import { ActiveRoutePage } from '@/pages/ActiveRoute'
import { OrderDetailPage } from '@/pages/OrderDetail'
import { EarningsPage } from '@/pages/Earnings'
import { ProfilePage } from '@/pages/Profile'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1 } },
})

function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function RequireGuest({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return !isAuthenticated ? <>{children}</> : <Navigate to="/" replace />
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>

          {/* Public routes — only accessible when NOT logged in */}
          <Route element={<RequireGuest><AuthLayout /></RequireGuest>}>
            <Route path="/login"    element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>

          {/* Protected routes */}
          <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
            <Route path="/"          element={<HomePage />} />
            <Route path="/orders"    element={<OrdersPage />} />
            <Route path="/orders/:id" element={<OrderDetailPage />} />
            <Route path="/route"     element={<ActiveRoutePage />} />
            <Route path="/earnings"  element={<EarningsPage />} />
            <Route path="/profile"   element={<ProfilePage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />

        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
