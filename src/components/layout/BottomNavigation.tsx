import { NavLink } from 'react-router-dom'
import { Home, ClipboardList, BarChart2, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useOrdersStore } from '@/stores/orders.store'

const navItems = [
  { to: '/', label: 'Inicio', Icon: Home, exact: true, badge: false },
  { to: '/orders', label: 'Pedidos', Icon: ClipboardList, exact: false, badge: true },
  { to: '/earnings', label: 'Ganancias', Icon: BarChart2, exact: false, badge: false },
  { to: '/profile', label: 'Perfil', Icon: User, exact: false, badge: false },
]

export function BottomNavigation() {
  const activeOrders = useOrdersStore((s) => s.activeOrders)
  const badgeCount = activeOrders.length

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 flex justify-center"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <div className="w-full max-w-[430px] bg-vygo-card/95 backdrop-blur-xl border-t border-vygo-border">
        <div className="flex items-center justify-around px-2 pt-2 pb-3">
          {navItems.map(({ to, label, Icon, exact, badge }) => (
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
                  <div className="relative">
                    <Icon
                      size={22}
                      strokeWidth={isActive ? 2.5 : 1.8}
                      className={cn('transition-all duration-200', isActive && 'drop-shadow-[0_0_8px_rgba(0,200,117,0.5)]')}
                    />
                    {badge && badgeCount > 0 && (
                      <span className="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 rounded-full bg-vygo-green text-[9px] font-bold text-vygo-bg flex items-center justify-center px-1 leading-none">
                        {badgeCount}
                      </span>
                    )}
                  </div>
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
