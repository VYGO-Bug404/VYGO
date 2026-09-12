import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-vygo-green/15 text-vygo-green',
        excellent: 'bg-vygo-green/15 text-vygo-green',
        good: 'bg-emerald-500/15 text-emerald-400',
        neutral: 'bg-vygo-secondary/15 text-vygo-secondary',
        bad: 'bg-vygo-danger/15 text-vygo-danger',
        warning: 'bg-vygo-warning/15 text-vygo-warning',
        online: 'bg-vygo-green/15 text-vygo-green',
        offline: 'bg-vygo-secondary/15 text-vygo-secondary',
        uber: 'bg-white/10 text-white',
        rappi: 'bg-red-500/15 text-red-400',
        didi: 'bg-orange-500/15 text-orange-400',
        secondary: 'bg-vygo-card-2 text-vygo-secondary',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
