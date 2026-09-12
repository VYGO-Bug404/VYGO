import { useState } from 'react'
import { useOrdersStore } from '@/stores/orders.store'
import { PageHeader } from '@/components/layout/PageHeader'
import { OrderCard } from '@/components/orders/OrderCard'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { formatCurrency, formatMinutes, formatDistance } from '@/lib/utils'
import { Package } from 'lucide-react'

export function OrdersPage() {
  const activeOrders = useOrdersStore((s) => s.activeOrders)
  const completedOrders = useOrdersStore((s) => s.completedOrders)
  const [activeTab, setActiveTab] = useState('active')

  const totalActiveEarnings = activeOrders.reduce((sum, o) => sum + o.earnings, 0)
  const totalActiveMinutes = activeOrders.reduce((sum, o) => sum + o.estimatedMinutes, 0)
  const totalActiveKm = activeOrders.reduce((sum, o) => sum + o.distanceKm, 0)

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader title="Mis pedidos" />

      <div className="px-4 pb-4">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full">
            <TabsTrigger value="active" className="flex-1">
              En curso{activeOrders.length > 0 && ` (${activeOrders.length})`}
            </TabsTrigger>
            <TabsTrigger value="completed" className="flex-1">
              Completados{completedOrders.length > 0 && ` (${completedOrders.length})`}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="active">
            {activeOrders.length === 0 ? (
              <EmptyState label="No tienes pedidos activos" />
            ) : (
              <div className="space-y-3">
                {/* Timeline */}
                <div className="relative">
                  {activeOrders.map((order, i) => (
                    <div key={order.id} className="flex gap-3 mb-3">
                      {/* Timeline indicator */}
                      <div className="flex flex-col items-center pt-1.5">
                        <div className="w-7 h-7 rounded-full bg-vygo-green flex items-center justify-center text-[11px] font-bold text-vygo-bg flex-shrink-0 z-10">
                          {i + 1}
                        </div>
                        {i < activeOrders.length - 1 && (
                          <div className="w-0.5 flex-1 min-h-[12px] bg-vygo-border mt-1" />
                        )}
                      </div>
                      <div className="flex-1">
                        <OrderCard order={order} className="flex-1" />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Active route summary */}
                <div className="bg-vygo-card border border-vygo-border rounded-2xl p-4 mt-4">
                  <p className="text-xs text-vygo-secondary font-medium uppercase tracking-wide mb-3">
                    Ruta actual
                  </p>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="text-center">
                      <p className="text-xl font-bold text-vygo-green text-money">
                        {formatCurrency(totalActiveEarnings)}
                      </p>
                      <p className="text-xs text-vygo-secondary mt-0.5">Ganancia</p>
                    </div>
                    <div className="text-center border-x border-vygo-border">
                      <p className="text-xl font-bold text-vygo-white">
                        {formatMinutes(totalActiveMinutes)}
                      </p>
                      <p className="text-xs text-vygo-secondary mt-0.5">Tiempo</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xl font-bold text-vygo-white">
                        {formatDistance(totalActiveKm)}
                      </p>
                      <p className="text-xs text-vygo-secondary mt-0.5">Distancia</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="completed">
            {completedOrders.length === 0 ? (
              <EmptyState label="Aún no has completado pedidos hoy" />
            ) : (
              <div className="space-y-2">
                {completedOrders.map((order) => (
                  <OrderCard key={order.id} order={order} />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <Package size={36} className="text-vygo-secondary/40" />
      <p className="text-sm text-vygo-secondary">{label}</p>
    </div>
  )
}
