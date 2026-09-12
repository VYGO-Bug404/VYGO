import { useParams, useNavigate } from 'react-router-dom'
import { Map, AlertCircle } from 'lucide-react'
import { useOrdersStore } from '@/stores/orders.store'
import { PageHeader } from '@/components/layout/PageHeader'
import { PlatformBadge } from '@/components/PlatformBadge'
import { OrderTimeline } from '@/components/orders/OrderTimeline'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatCurrencyDecimal, formatDistance, formatMinutes } from '@/lib/utils'
import { cn } from '@/lib/utils'

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  heading_to_pickup: { label: 'En ruta', className: 'bg-vygo-warning/15 text-vygo-warning border-vygo-warning/20' },
  accepted: { label: 'Aceptado', className: 'bg-vygo-green/15 text-vygo-green border-vygo-green/20' },
  picked_up: { label: 'Recogido', className: 'bg-vygo-green/15 text-vygo-green border-vygo-green/20' },
  delivered: { label: 'Entregado', className: 'bg-vygo-secondary/15 text-vygo-secondary border-vygo-secondary/20' },
  offered: { label: 'Ofertado', className: 'bg-vygo-warning/15 text-vygo-warning border-vygo-warning/20' },
}

export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const activeOrders = useOrdersStore((s) => s.activeOrders)
  const completedOrders = useOrdersStore((s) => s.completedOrders)

  const order = [...activeOrders, ...completedOrders].find((o) => o.id === id)

  if (!order) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 px-4">
        <p className="text-vygo-secondary text-center">Pedido no encontrado.</p>
        <Button variant="ghost" onClick={() => navigate(-1)}>
          Volver
        </Button>
      </div>
    )
  }

  const statusConfig = STATUS_LABELS[order.status] ?? { label: order.status, className: 'bg-vygo-secondary/15 text-vygo-secondary border-vygo-secondary/20' }
  const earningsPerKm = order.earningsPerKm ?? (order.earnings / order.distanceKm)

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title={`Pedido #${order.orderNumber}`}
        showBack
        right={<PlatformBadge platform={order.platform} size="md" />}
      />

      <div className="px-4 pb-8 space-y-4">
        {/* Hero */}
        <div className="bg-vygo-card border border-vygo-border rounded-2xl p-4">
          <div className="flex items-start justify-between mb-3">
            <div>
              <span className={cn('inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold', statusConfig.className)}>
                {statusConfig.label}
              </span>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-vygo-green text-money">
                {formatCurrency(order.earnings)}
              </p>
              <p className="text-xs text-vygo-secondary">ganancia total</p>
            </div>
          </div>
        </div>

        {/* Timeline */}
        <div className="bg-vygo-card border border-vygo-border rounded-2xl p-4">
          <OrderTimeline order={order} />
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-3 gap-2">
          <MetricTile value={formatMinutes(order.estimatedMinutes)} label="Tiempo estimado" />
          <MetricTile value={formatDistance(order.distanceKm)} label="Distancia" />
          <MetricTile
            value={formatCurrencyDecimal(earningsPerKm)}
            label="Ganancia/km"
            highlight
          />
        </div>

        {/* Actions */}
        <div className="space-y-2">
          <Button variant="secondary" size="default" className="w-full h-12 gap-2">
            <Map size={16} />
            Abrir en Maps
          </Button>

          {order.status !== 'delivered' && (
            <Button
              variant="ghost"
              size="default"
              className="w-full h-11 text-vygo-danger hover:text-vygo-danger gap-2"
            >
              <AlertCircle size={15} />
              Reportar problema
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricTile({ value, label, highlight = false }: { value: string; label: string; highlight?: boolean }) {
  return (
    <div className="bg-vygo-card border border-vygo-border rounded-2xl p-3 text-center">
      <p className={cn('text-base font-bold text-money leading-tight', highlight ? 'text-vygo-green' : 'text-vygo-white')}>
        {value}
      </p>
      <p className="text-[10px] text-vygo-secondary mt-0.5 leading-tight">{label}</p>
    </div>
  )
}
