interface VygoLogoProps {
  variant?: 'dark' | 'white'
  className?: string
  height?: number
}

export function VygoLogo({ variant = 'dark', className = '', height = 36 }: VygoLogoProps) {
  return (
    <img
      src="/vygo-logo-black.png"
      alt="VYGO"
      height={height}
      style={{
        height,
        width: 'auto',
        filter: variant === 'white' ? 'invert(1)' : 'none',
        display: 'block',
      }}
      className={className}
    />
  )
}
