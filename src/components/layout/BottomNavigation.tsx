import { NavLink } from 'react-router-dom'
import { Home, ClipboardList, BarChart2, User } from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', label: 'Inicio', Icon: Home, exact: true },
  { to: '/orders', label: 'Pedidos', Icon: ClipboardList, exact: false },
  { to: '/earnings', label: 'Ganancias', Icon: BarChart2, exact: false },
  { to: '/profile', label: 'Perfil', Icon: User, exact: false },
]

export function BottomNavigation() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 flex justify-center"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <div className="w-full max-w-[430px] bg-vygo-card/95 backdrop-blur-xl border-t border-vygo-border">
        <div className="flex items-center justify-around px-2 pt-2 pb-3">
          {navItems.map(({ to, label, Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center gap-1 min-w-[64px] py-1 px-2 rounded-xl transition-all duration-200',
                  isActive ? 'text-vygo-green' : 'text-vygo-secondary'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    size={22}
                    strokeWidth={isActive ? 2.5 : 1.8}
                    className={cn('transition-all duration-200', isActive && 'drop-shadow-[0_0_8px_rgba(0,200,117,0.5)]')}
                  />
                  <span className={cn('text-[10px] font-medium leading-none', isActive && 'font-semibold')}>
                    {label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  )
}
