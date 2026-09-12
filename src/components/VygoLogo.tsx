interface VygoLogoProps {
  variant?: 'dark' | 'white'
  className?: string
  height?: number
}

// Aspect ratio del logo: 3.57:1 (340 x 104 px después de recorte ajustado)
const ASPECT_RATIO = 340 / 104

export function VygoLogo({ variant = 'dark', className = '', height = 36 }: VygoLogoProps) {
  return (
    <img
      src="/vygo-logo-black.png"
      alt="VYGO"
      style={{
        height: `${height}px`,
        width: `${Math.round(height * ASPECT_RATIO)}px`,
        objectFit: 'contain',
        display: 'block',
        filter: variant === 'white' ? 'invert(1)' : 'none',
        flexShrink: 0,
      }}
      className={className}
    />
  )
}
