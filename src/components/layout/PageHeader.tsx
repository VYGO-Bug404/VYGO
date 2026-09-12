import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: string
  subtitle?: string
  showBack?: boolean
  right?: React.ReactNode
  className?: string
}

export function PageHeader({ title, subtitle, showBack = false, right, className }: PageHeaderProps) {
  const navigate = useNavigate()

  return (
    <div
      className={cn(
        'flex items-center justify-between px-4 py-4',
        className
      )}
      style={{ paddingTop: `max(env(safe-area-inset-top, 0px), 16px)` }}
    >
      <div className="flex items-center gap-3">
        {showBack && (
          <button
            onClick={() => navigate(-1)}
            className="flex items-center justify-center w-9 h-9 rounded-xl bg-vygo-card border border-vygo-border text-vygo-secondary hover:text-vygo-white transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
        )}
        <div>
          <h1 className="text-xl font-semibold text-vygo-white leading-tight">{title}</h1>
          {subtitle && <p className="text-sm text-vygo-secondary">{subtitle}</p>}
        </div>
      </div>
      {right && <div>{right}</div>}
    </div>
  )
}
