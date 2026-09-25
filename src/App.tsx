import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
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
import { EmpresaPage } from '@/pages/Empresa'

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
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route element={<RequireGuest><AuthLayout /></RequireGuest>}>
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
          <Route path="/"           element={<HomePage />} />
          <Route path="/orders"     element={<OrdersPage />} />
          <Route path="/orders/:id" element={<OrderDetailPage />} />
          <Route path="/route"      element={<ActiveRoutePage />} />
          <Route path="/earnings"   element={<EarningsPage />} />
          <Route path="/profile"    element={<ProfilePage />} />
          <Route path="/empresa"    element={<EmpresaPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
