import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, Eye, EyeOff } from 'lucide-react'
import { useAuthStore } from '@/stores/auth.store'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState<{ email?: string; password?: string; general?: string }>({})

  const validate = () => {
    const e: typeof errors = {}
    if (!email) e.email = 'Ingresa tu correo'
    else if (!/\S+@\S+\.\S+/.test(email)) e.email = 'Correo inválido'
    if (!password) e.password = 'Ingresa tu contraseña'
    return e
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    setErrors({})
    setLoading(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch {
      setErrors({ general: 'Correo o contraseña incorrectos' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="flex flex-col min-h-full px-6"
      style={{ paddingTop: `max(env(safe-area-inset-top, 0px), 48px)` }}
    >
      {/* Logo */}
      <div className="flex flex-col items-center mb-10">
        <div className="mb-4">
          <VygoLogo />
        </div>
        <p className="text-sm text-vygo-secondary font-medium tracking-wide">
          Muévete mejor. Gana más.
        </p>
      </div>

      {/* Heading */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-vygo-white mb-1">Bienvenido de vuelta</h1>
        <p className="text-sm text-vygo-secondary">Inicia sesión para continuar</p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {errors.general && (
          <div className="bg-vygo-danger/10 border border-vygo-danger/30 rounded-2xl px-4 py-3">
            <p className="text-sm text-vygo-danger">{errors.general}</p>
          </div>
        )}

        <Input
          label="Correo electrónico"
          type="email"
          placeholder="tu@correo.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
          leftIcon={<Mail size={16} />}
          autoComplete="email"
          inputMode="email"
        />

        <Input
          label="Contraseña"
          type={showPassword ? 'text' : 'password'}
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.password}
          leftIcon={<Lock size={16} />}
          rightElement={
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="text-vygo-secondary hover:text-vygo-white transition-colors"
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          }
          autoComplete="current-password"
        />

        <div className="flex justify-end -mt-1">
          <button type="button" className="text-xs text-vygo-secondary hover:text-vygo-white transition-colors">
            ¿Olvidaste tu contraseña?
          </button>
        </div>

        <Button
          type="submit"
          size="xl"
          className="w-full h-14 text-base font-semibold mt-2"
          disabled={loading}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-vygo-bg/50 border-t-vygo-bg rounded-full animate-spin" />
              Ingresando…
            </span>
          ) : 'Iniciar sesión'}
        </Button>
      </form>

      {/* Divider */}
      <div className="flex items-center gap-3 my-6">
        <div className="flex-1 h-px bg-vygo-border" />
        <span className="text-xs text-vygo-secondary">¿No tienes cuenta?</span>
        <div className="flex-1 h-px bg-vygo-border" />
      </div>

      {/* Register link */}
      <Link
        to="/register"
        className="flex items-center justify-center w-full h-13 rounded-2xl border border-vygo-border text-vygo-white text-[15px] font-medium hover:border-vygo-green/40 hover:text-vygo-green transition-all duration-200 py-3.5"
      >
        Crear una cuenta
      </Link>

      <p className="text-center text-[11px] text-vygo-secondary/40 mt-8 pb-8">
        Al continuar aceptas los Términos de uso y la Política de privacidad de VYGO.
      </p>
    </div>
  )
}

function VygoLogo() {
  return (
    <div className="flex items-center gap-0">
      <span
        className="text-[42px] font-black tracking-[-2px] text-vygo-white leading-none select-none"
        style={{ fontFamily: 'Inter, sans-serif' }}
      >
        VY
      </span>
      <span
        className="text-[42px] font-black tracking-[-2px] text-vygo-green leading-none select-none"
        style={{ fontFamily: 'Inter, sans-serif' }}
      >
        GO
      </span>
    </div>
  )
}
