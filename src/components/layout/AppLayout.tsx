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
    /* ── Outer shell: white on mobile, brand-indigo on desktop ── */
    <div className="flex justify-center items-start lg:items-center w-full h-full bg-vygo-bg lg:bg-[#0E1145] relative overflow-hidden">

      {/* ── Desktop background decorations ── */}
      <div className="hidden lg:block pointer-events-none select-none">
        {/* Glow blobs */}
        <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full bg-[#C9E86E]/5 blur-[120px]" />
        <div className="absolute bottom-1/3 right-1/4 w-[350px] h-[350px] rounded-full bg-[#6FA800]/6 blur-[100px]" />

        {/* VYGO brand — top left */}
        <div className="absolute top-10 left-12 flex flex-col gap-1">
          <div className="flex items-center leading-none">
            <span className="text-5xl font-black text-white tracking-[-2px]">VY</span>
            <span className="text-5xl font-black text-[#C9E86E] tracking-[-2px]">GO</span>
          </div>
          <p className="text-[#7880C8] text-sm font-medium">Muévete mejor. Gana más.</p>
        </div>

        {/* Tagline — bottom left */}
        <div className="absolute bottom-10 left-12">
          <p className="text-[#3A4090] text-xs font-medium tracking-wide uppercase">
            DeliveryTech · Monterrey
          </p>
        </div>
      </div>

      {/* ── Phone frame ── */}
      <div
        className={[
          // Base (mobile)
          'relative flex flex-col w-full max-w-[430px] h-full overflow-hidden bg-vygo-bg',
          // Desktop frame
          'lg:w-[390px] lg:max-w-none lg:h-[min(844px,calc(100vh-40px))]',
          'lg:rounded-[52px] lg:border-[10px] lg:border-[#1a1f6e]',
          'lg:shadow-phone',
        ].join(' ')}
      >
        {/* Dynamic island — desktop only */}
        <div className="hidden lg:flex absolute top-3 left-1/2 -translate-x-1/2 z-50
                        w-[110px] h-[30px] bg-[#0F1340] rounded-full
                        items-center justify-center gap-2 pointer-events-none">
          <div className="w-2 h-2 rounded-full bg-[#1a2055]" />
          <div className="w-5 h-1.5 rounded-full bg-[#1a2055]" />
        </div>

        {/* Side buttons — desktop only */}
        <div className="hidden lg:block absolute left-[-18px] top-28 w-[8px] h-10 bg-[#141860] rounded-l-md" />
        <div className="hidden lg:block absolute left-[-18px] top-44 w-[8px] h-14 bg-[#141860] rounded-l-md" />
        <div className="hidden lg:block absolute left-[-18px] top-[248px] w-[8px] h-14 bg-[#141860] rounded-l-md" />
        <div className="hidden lg:block absolute right-[-18px] top-36 w-[8px] h-20 bg-[#141860] rounded-r-md" />

        {/* ── Content ── */}
        {isRouteScreen ? (
          <main className="flex-1 overflow-hidden min-h-0 lg:pt-0">
            <Outlet />
          </main>
        ) : (
          <main className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-none pb-[72px] min-h-0 lg:pt-8">
            <Outlet />
          </main>
        )}

        {!isRouteScreen && <BottomNavigation />}

        {/* Home indicator — desktop only */}
        <div className="hidden lg:flex justify-center py-2 bg-vygo-bg shrink-0">
          <div className="w-32 h-1 bg-vygo-border rounded-full" />
        </div>

        {pendingOffer && <NewOrderSheet order={pendingOffer} />}

        {driverStatus !== 'offline' && !pendingOffer && !isRouteScreen && (
          <button
            onClick={simulateNewOrder}
            className="fixed bottom-24 right-4 z-30 flex items-center gap-2 bg-vygo-card border border-vygo-border text-vygo-secondary text-xs font-medium px-3 py-2 rounded-full shadow-card hover:text-vygo-white transition-colors lg:absolute"
          >
            <Zap size={12} className="text-vygo-warning" />
            Simular pedido
          </button>
        )}
      </div>
    </div>
  )
}
