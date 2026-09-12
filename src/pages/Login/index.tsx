import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, Eye, EyeOff, ArrowLeft, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores/auth.store'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

type Step = 'main' | 'email'

export function LoginPage() {
  const navigate = useNavigate()
  const { signInWithApple, signInWithGoogle, login } = useAuthStore()

  const [step, setStep] = useState<Step>('main')
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)

  const clearError = () => setErrorMsg(null)

  const withLoader = async (fn: () => Promise<void>) => {
    setLoading(true)
    clearError()
    try {
      await fn()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Error desconocido'
      setErrorMsg(
        msg.includes('Invalid login')
          ? 'Correo o contraseña incorrectos'
          : msg
      )
    } finally {
      setLoading(false)
    }
  }

  const handleApple = () => withLoader(() => signInWithApple())
  const handleGoogle = () => withLoader(() => signInWithGoogle())

  const handleEmailLogin = () =>
    withLoader(async () => {
      await login(email, password)
      navigate('/', { replace: true })
    })

  return (
    <div
      className="flex flex-col min-h-full px-6"
      style={{ paddingTop: `max(env(safe-area-inset-top, 0px), 48px)` }}
    >
      {/* Logo */}
      <div className="flex flex-col items-center mb-10">
        <VygoLogo />
        <p className="text-sm text-vygo-secondary font-medium tracking-wide mt-3">
          Muévete mejor. Gana más.
        </p>
      </div>

      {/* ── STEP: main ── */}
      {step === 'main' && (
        <>
          <div className="mb-7">
            <h1 className="text-2xl font-bold text-vygo-white mb-1">Bienvenido</h1>
            <p className="text-sm text-vygo-secondary">Elige cómo iniciar sesión</p>
          </div>

          {errorMsg && <ErrorBanner msg={errorMsg} onClose={clearError} />}

          <div className="flex flex-col gap-3">
            <SocialButton
              onClick={handleApple}
              loading={loading}
              icon={<AppleLogo />}
              label="Continuar con Apple"
              className="bg-white text-black hover:bg-gray-100"
            />
            <SocialButton
              onClick={handleGoogle}
              loading={loading}
              icon={<GoogleLogo />}
              label="Continuar con Google"
              className="bg-vygo-card border border-vygo-border text-vygo-white hover:bg-vygo-card-2"
            />
          </div>

          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-vygo-border" />
            <span className="text-xs text-vygo-secondary">o usa tu correo</span>
            <div className="flex-1 h-px bg-vygo-border" />
          </div>

          <button
            onClick={() => { clearError(); setStep('email') }}
            className="flex items-center justify-center w-full h-13 rounded-2xl border border-vygo-border text-vygo-secondary text-sm font-medium hover:border-vygo-green/40 hover:text-vygo-green transition-all duration-200 py-3.5"
          >
            Iniciar sesión con correo
          </button>

          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-vygo-border" />
            <span className="text-xs text-vygo-secondary">¿No tienes cuenta?</span>
            <div className="flex-1 h-px bg-vygo-border" />
          </div>

          <Link
            to="/register"
            className="flex items-center justify-center w-full h-13 rounded-2xl border border-vygo-green/30 text-vygo-green text-[15px] font-medium hover:bg-vygo-green/5 transition-all duration-200 py-3.5"
          >
            Crear una cuenta
          </Link>
        </>
      )}

      {/* ── STEP: email ── */}
      {step === 'email' && (
        <>
          <BackButton onClick={() => { clearError(); setStep('main') }} />
          <div className="mb-7">
            <h1 className="text-2xl font-bold text-vygo-white mb-1">Iniciar sesión</h1>
            <p className="text-sm text-vygo-secondary">Con tu correo y contraseña</p>
          </div>

          {errorMsg && <ErrorBanner msg={errorMsg} onClose={clearError} />}

          <div className="flex flex-col gap-4">
            <Input
              label="Correo electrónico"
              type="email"
              placeholder="tu@correo.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              leftIcon={<Mail size={16} />}
              autoComplete="email"
              inputMode="email"
            />
            <Input
              label="Contraseña"
              type={showPwd ? 'text' : 'password'}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              leftIcon={<Lock size={16} />}
              rightElement={
                <button type="button" onClick={() => setShowPwd(!showPwd)} className="text-vygo-secondary">
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
              autoComplete="current-password"
            />
            <Button
              onClick={handleEmailLogin}
              disabled={loading || !email || !password}
              size="xl"
              className="w-full h-14 text-base font-semibold mt-2"
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : 'Iniciar sesión'}
            </Button>
          </div>
        </>
      )}

      <p className="text-center text-[11px] text-vygo-secondary/40 mt-auto pb-8 pt-8">
        Al continuar aceptas los Términos de uso y la Política de privacidad de VYGO.
      </p>
    </div>
  )
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 text-vygo-secondary hover:text-vygo-white transition-colors text-sm mb-6 -ml-1"
    >
      <ArrowLeft size={16} /> Volver
    </button>
  )
}

function ErrorBanner({ msg, onClose }: { msg: string; onClose: () => void }) {
  return (
    <div className="bg-vygo-danger/10 border border-vygo-danger/30 rounded-2xl px-4 py-3 mb-4 flex items-start justify-between gap-2">
      <p className="text-sm text-vygo-danger flex-1">{msg}</p>
      <button onClick={onClose} className="text-vygo-danger/60 hover:text-vygo-danger mt-0.5">
        <XIcon />
      </button>
    </div>
  )
}

function SocialButton({
  onClick, loading, icon, label, className,
}: {
  onClick: () => void
  loading: boolean
  icon: React.ReactNode
  label: string
  className: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`flex items-center justify-center gap-3 w-full h-14 rounded-2xl text-[15px] font-semibold transition-all duration-200 disabled:opacity-60 ${className}`}
    >
      <span className="w-5 h-5 flex items-center justify-center flex-shrink-0">{icon}</span>
      {label}
    </button>
  )
}

function VygoLogo() {
  return (
    <div className="flex items-center">
      <span className="text-[42px] font-black tracking-[-2px] text-vygo-white leading-none select-none">VY</span>
      <span className="text-[42px] font-black tracking-[-2px] text-vygo-green leading-none select-none">GO</span>
    </div>
  )
}

function AppleLogo() {
  return (
    <svg width="17" height="20" viewBox="0 0 814 1000" fill="currentColor">
      <path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76 0-103.7 40.8-165.9 40.8s-105-37.3-161.1-100.6C149.1 680.2 111.4 582 111.4 488.7c0-160.8 104.3-245.7 206.4-245.7 58.2 0 106.7 37.3 143.5 37.3 35.5 0 90.3-39.5 155.4-39.5 24.7 0 108.2 2.6 168.6 74.3zm-209.7-220c28.5-35 48.7-83.8 48.7-132.6 0-6.5-.6-13.1-1.9-18.3-45.6 1.9-99.4 30.4-131.8 70.6-25.1 29.1-48.7 77.9-48.7 127.4 0 7.1 1.3 14.3 1.9 16.6 3.2.6 8.4 1.3 13.6 1.3 40.8 0 92.1-26.5 118.2-65z"/>
    </svg>
  )
}

function GoogleLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
  )
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 6 6 18M6 6l12 12"/>
    </svg>
  )
}
