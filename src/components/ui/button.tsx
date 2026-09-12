import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-2xl text-sm font-semibold transition-all duration-150 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-vygo-green disabled:pointer-events-none disabled:opacity-40 select-none',
  {
    variants: {
      variant: {
        default: 'bg-vygo-green text-vygo-bg hover:bg-vygo-green-bright',
        destructive: 'bg-transparent border-2 border-vygo-danger text-vygo-danger hover:bg-vygo-danger/10',
        outline: 'border border-vygo-border bg-transparent text-vygo-white hover:bg-vygo-card',
        ghost: 'bg-transparent text-vygo-secondary hover:bg-vygo-card hover:text-vygo-white',
        secondary: 'bg-vygo-card text-vygo-white hover:bg-vygo-card-2',
        link: 'text-vygo-green underline-offset-4 hover:underline p-0 h-auto',
      },
      size: {
        default: 'h-12 px-6 py-3 text-[15px]',
        sm: 'h-9 px-4 text-sm',
        lg: 'h-14 px-8 text-[16px]',
        xl: 'h-16 px-8 text-[17px]',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
