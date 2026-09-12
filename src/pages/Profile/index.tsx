import {
  User,
  Bike,
  Bell,
  HelpCircle,
  LogOut,
  ChevronRight,
  Shield,
  Star,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useDriverStore } from '@/stores/driver.store'
import { useAuthStore } from '@/stores/auth.store'
import { PlatformBadge } from '@/components/PlatformBadge'
import { PageHeader } from '@/components/layout/PageHeader'
import type { Platform } from '@/types/order'

export function ProfilePage() {
  const navigate = useNavigate()
  const driver = useDriverStore((s) => s.driver)
  const endShift = useDriverStore((s) => s.endShift)
  const status = useDriverStore((s) => s.status)
  const logout = useAuthStore((s) => s.logout)

  const handleLogout = () => {
    endShift()
    logout()
    navigate('/login', { replace: true })
  }

  const menuItems = [
    { icon: User, label: 'Información personal', subtitle: driver.name },
    {
      icon: Bike,
      label: 'Vehículo',
      subtitle: `${driver.vehicle.type === 'moto' ? 'Moto' : 'Auto'} · ${driver.vehicle.brand} ${driver.vehicle.model}`,
    },
    {
      icon: Shield,
      label: 'Plataformas conectadas',
      subtitle: `${driver.platforms.length} conectadas`,
      content: (
        <div className="flex items-center gap-1.5 mt-1.5">
          {driver.platforms.map((p) => (
            <PlatformBadge key={p} platform={p as Platform} size="sm" />
          ))}
        </div>
      ),
    },
    { icon: Bell, label: 'Notificaciones' },
    { icon: HelpCircle, label: 'Soporte' },
  ]

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader title="Perfil" />

      <div className="px-4 pb-8 space-y-4">
        {/* Avatar & name */}
        <div className="flex flex-col items-center py-4 gap-3">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-vygo-green/15 border-2 border-vygo-green/30 flex items-center justify-center">
              <span className="text-2xl font-bold text-vygo-green">{driver.avatarInitials}</span>
            </div>
            <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-vygo-green flex items-center justify-center">
              <Star size={12} className="text-vygo-bg" fill="currentColor" />
            </div>
          </div>
          <div className="text-center">
            <h2 className="text-xl font-semibold text-vygo-white">{driver.name} Gabuardi</h2>
            <p className="text-sm text-vygo-secondary">Repartidor verificado</p>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-6">
            <div className="text-center">
              <p className="text-lg font-bold text-vygo-white">{driver.rating}</p>
              <p className="text-xs text-vygo-secondary">Rating</p>
            </div>
            <div className="w-px h-8 bg-vygo-border" />
            <div className="text-center">
              <p className="text-lg font-bold text-vygo-white">{driver.totalDeliveries.toLocaleString()}</p>
              <p className="text-xs text-vygo-secondary">Entregas</p>
            </div>
            <div className="w-px h-8 bg-vygo-border" />
            <div className="text-center">
              <p className="text-lg font-bold text-vygo-white">{driver.memberSince.split(' ')[1]}</p>
              <p className="text-xs text-vygo-secondary">Desde {driver.memberSince.split(' ')[0]}</p>
            </div>
          </div>
        </div>

        {/* Menu */}
        <div className="bg-vygo-card border border-vygo-border rounded-2xl overflow-hidden divide-y divide-vygo-border">
          {menuItems.map(({ icon: Icon, label, subtitle, content }) => (
            <button
              key={label}
              className="flex items-center gap-3 px-4 py-3.5 w-full text-left hover:bg-vygo-card-2 transition-colors"
            >
              <div className="w-8 h-8 rounded-xl bg-vygo-card-2 flex items-center justify-center flex-shrink-0">
                <Icon size={16} className="text-vygo-secondary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-vygo-white">{label}</p>
                {subtitle && <p className="text-xs text-vygo-secondary truncate">{subtitle}</p>}
                {content}
              </div>
              <ChevronRight size={16} className="text-vygo-secondary flex-shrink-0" />
            </button>
          ))}
        </div>

        {/* Logout */}
        {status !== 'offline' && (
          <button
            onClick={endShift}
            className="flex items-center justify-center gap-2 w-full h-12 rounded-2xl border border-vygo-danger/30 bg-vygo-danger/5 text-vygo-danger text-sm font-semibold hover:bg-vygo-danger/10 transition-colors"
          >
            <LogOut size={16} />
            Finalizar jornada
          </button>
        )}

        <button
          onClick={handleLogout}
          className="flex items-center justify-center gap-2 w-full h-12 rounded-2xl border border-vygo-border bg-transparent text-vygo-secondary text-sm font-medium hover:text-vygo-white transition-colors"
        >
          <LogOut size={16} />
          Cerrar sesión
        </button>

        {/* Version */}
        <p className="text-center text-[11px] text-vygo-secondary/50 pb-2">
          VYGO v0.1.0 · Muévete mejor. Gana más.
        </p>
      </div>
    </div>
  )
}
