import { Outlet, useLocation } from 'react-router-dom'
import { BottomNavigation } from './BottomNavigation'
import { NewOrderSheet } from '@/components/orders/NewOrderSheet'
import { useOrdersStore } from '@/stores/orders.store'
import { useDriverStore } from '@/stores/driver.store'
import { useNewOrder } from '@/hooks/useNewOrder'
import { useLocationTracking } from '@/hooks/useLocationTracking'
import { Zap } from 'lucide-react'

export function AppLayout() {
  useNewOrder()
  useLocationTracking()

  const location = useLocation()
  const isRouteScreen = location.pathname === '/route'

  const pendingOffer = useOrdersStore((s) => s.pendingOffer)
  const simulateNewOrder = useOrdersStore((s) => s.simulateNewOrder)
  const driverStatus = useDriverStore((s) => s.status)

  return (
    <div className="flex justify-center w-full h-full bg-black">
      <div className="relative w-full max-w-[430px] h-full flex flex-col overflow-hidden bg-vygo-bg">

        {isRouteScreen ? (
          /* Route screen: full height, no scroll, no bottom padding */
          <main className="flex-1 overflow-hidden min-h-0">
            <Outlet />
          </main>
        ) : (
          /* Normal screens: scrollable with room for bottom nav */
          <main className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-none pb-[72px] min-h-0">
            <Outlet />
          </main>
        )}

        {!isRouteScreen && <BottomNavigation />}

        {pendingOffer && <NewOrderSheet order={pendingOffer} />}

        {driverStatus !== 'offline' && !pendingOffer && !isRouteScreen && (
          <button
            onClick={simulateNewOrder}
            className="fixed bottom-24 right-4 z-30 flex items-center gap-2 bg-vygo-card-2 border border-vygo-border text-vygo-secondary text-xs font-medium px-3 py-2 rounded-full shadow-card hover:text-vygo-white transition-colors"
          >
            <Zap size={12} className="text-vygo-warning" />
            Simular pedido
          </button>
        )}
      </div>
    </div>
  )
}
