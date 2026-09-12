import * as React from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  leftIcon?: React.ReactNode
  rightElement?: React.ReactNode
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, leftIcon, rightElement, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label className="text-sm font-medium text-vygo-secondary">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {leftIcon && (
            <div className="absolute left-3.5 text-vygo-secondary pointer-events-none">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            className={cn(
              'w-full h-13 rounded-2xl bg-vygo-card-2 border border-vygo-border',
              'text-vygo-white text-[15px] placeholder:text-vygo-secondary/50',
              'transition-all duration-150 outline-none',
              'focus:border-vygo-green focus:ring-1 focus:ring-vygo-green/30',
              error && 'border-vygo-danger focus:border-vygo-danger focus:ring-vygo-danger/30',
              leftIcon ? 'pl-11' : 'pl-4',
              rightElement ? 'pr-11' : 'pr-4',
              'py-3.5',
              className
            )}
            {...props}
          />
          {rightElement && (
            <div className="absolute right-3.5">
              {rightElement}
            </div>
          )}
        </div>
        {error && (
          <p className="text-xs text-vygo-danger">{error}</p>
        )}
      </div>
    )
  }
)
Input.displayName = 'Input'

export { Input }
