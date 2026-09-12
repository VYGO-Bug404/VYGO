import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { User, Mail, Lock, Eye, EyeOff, ArrowLeft, Phone } from 'lucide-react'
import { useAuthStore } from '@/stores/auth.store'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export function RegisterPage() {
  const navigate = useNavigate()
  const register = useAuthStore((s) => s.register)

  const [form, setForm] = useState({ name: '', email: '', phone: '', password: '', confirm: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  const validate = () => {
    const e: Record<string, string> = {}
    if (!form.name.trim()) e.name = 'Ingresa tu nombre'
    if (!form.email) e.email = 'Ingresa tu correo'
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Correo inválido'
    if (!form.password) e.password = 'Ingresa una contraseña'
    else if (form.password.length < 6) e.password = 'Mínimo 6 caracteres'
    if (!form.confirm) e.confirm = 'Confirma tu contraseña'
    else if (form.confirm !== form.password) e.confirm = 'Las contraseñas no coinciden'
    return e
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    setErrors({})
    setLoading(true)
    try {
      await register(form.name, form.email, form.password)
      navigate('/', { replace: true })
    } catch {
      setErrors({ general: 'No se pudo crear la cuenta. Intenta de nuevo.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="flex flex-col min-h-full px-6"
      style={{ paddingTop: `max(env(safe-area-inset-top, 0px), 16px)` }}
    >
      {/* Back */}
      <button
        onClick={() => navigate('/login')}
        className="w-9 h-9 flex items-center justify-center rounded-xl bg-vygo-card border border-vygo-border text-vygo-secondary hover:text-vygo-white transition-colors mb-8 self-start"
      >
        <ArrowLeft size={18} />
      </button>

      {/* Heading */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-vygo-white mb-1">Crea tu cuenta</h1>
        <p className="text-sm text-vygo-secondary">Empieza a ganar más desde hoy</p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {errors.general && (
          <div className="bg-vygo-danger/10 border border-vygo-danger/30 rounded-2xl px-4 py-3">
            <p className="text-sm text-vygo-danger">{errors.general}</p>
          </div>
        )}

        <Input
          label="Nombre completo"
          type="text"
          placeholder="Luis Gabuardi"
          value={form.name}
          onChange={set('name')}
          error={errors.name}
          leftIcon={<User size={16} />}
          autoComplete="name"
        />

        <Input
          label="Correo electrónico"
          type="email"
          placeholder="tu@correo.com"
          value={form.email}
          onChange={set('email')}
          error={errors.email}
          leftIcon={<Mail size={16} />}
          autoComplete="email"
          inputMode="email"
        />

        <Input
          label="Teléfono (opcional)"
          type="tel"
          placeholder="+52 81 1234 5678"
          value={form.phone}
          onChange={set('phone')}
          leftIcon={<Phone size={16} />}
          autoComplete="tel"
          inputMode="tel"
        />

        <Input
          label="Contraseña"
          type={showPassword ? 'text' : 'password'}
          placeholder="Mínimo 6 caracteres"
          value={form.password}
          onChange={set('password')}
          error={errors.password}
          leftIcon={<Lock size={16} />}
          rightElement={
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="text-vygo-secondary hover:text-vygo-white transition-colors">
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          }
          autoComplete="new-password"
        />

        <Input
          label="Confirmar contraseña"
          type={showConfirm ? 'text' : 'password'}
          placeholder="Repite tu contraseña"
          value={form.confirm}
          onChange={set('confirm')}
          error={errors.confirm}
          leftIcon={<Lock size={16} />}
          rightElement={
            <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="text-vygo-secondary hover:text-vygo-white transition-colors">
              {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          }
          autoComplete="new-password"
        />

        {/* Password strength */}
        {form.password.length > 0 && (
          <PasswordStrength password={form.password} />
        )}

        <Button
          type="submit"
          size="xl"
          className="w-full h-14 text-base font-semibold mt-2"
          disabled={loading}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-vygo-bg/50 border-t-vygo-bg rounded-full animate-spin" />
              Creando cuenta…
            </span>
          ) : 'Crear cuenta'}
        </Button>
      </form>

      <p className="text-center text-sm text-vygo-secondary mt-6">
        ¿Ya tienes cuenta?{' '}
        <Link to="/login" className="text-vygo-green font-semibold hover:text-vygo-green-bright transition-colors">
          Inicia sesión
        </Link>
      </p>

      <p className="text-center text-[11px] text-vygo-secondary/40 mt-6 pb-8">
        Al registrarte aceptas los Términos de uso y la Política de privacidad de VYGO.
      </p>
    </div>
  )
}

function PasswordStrength({ password }: { password: string }) {
  const strength = password.length < 6 ? 1 : password.length < 10 ? 2 : 3
  const labels = ['', 'Débil', 'Buena', 'Fuerte']
  const colors = ['', 'bg-vygo-danger', 'bg-vygo-warning', 'bg-vygo-green']
  const textColors = ['', 'text-vygo-danger', 'text-vygo-warning', 'text-vygo-green']

  return (
    <div className="flex items-center gap-2 -mt-1">
      <div className="flex gap-1 flex-1">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-all duration-300 ${
              i <= strength ? colors[strength] : 'bg-vygo-border'
            }`}
          />
        ))}
      </div>
      <span className={`text-xs font-medium ${textColors[strength]}`}>
        {labels[strength]}
      </span>
    </div>
  )
}
