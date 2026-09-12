import { useState } from 'react'
import { X, Check, ChevronRight, Loader2, Unplug } from 'lucide-react'
import { usePlatformConnections, type PlatformId } from '@/hooks/usePlatformConnections'
import { Button } from '@/components/ui/button'

interface Props {
  onClose: () => void
}

const PLATFORMS: { id: PlatformId; label: string; color: string; bg: string }[] = [
  { id: 'uber',  label: 'Uber Eats', color: '#FFFFFF', bg: '#000000' },
  { id: 'rappi', label: 'Rappi',     color: '#FFFFFF', bg: '#FF441A' },
  { id: 'didi',  label: 'DiDi Food', color: '#FFFFFF', bg: '#FF6600' },
]

export function PlatformConnectModal({ onClose }: Props) {
  const { connections, loading, connect, disconnect, isConnected, getConnection } =
    usePlatformConnections()

  // Which platform's connect-form is open
  const [expandedId, setExpandedId] = useState<PlatformId | null>(null)
  const [alias, setAlias] = useState('')
  const [saving, setSaving] = useState<PlatformId | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleConnect = async (platform: PlatformId) => {
    setSaving(platform)
    setError(null)
    try {
      await connect(platform, alias.trim() || undefined)
      setExpandedId(null)
      setAlias('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al conectar')
    } finally {
      setSaving(null)
    }
  }

  const handleDisconnect = async (platform: PlatformId) => {
    setSaving(platform)
    try {
      await disconnect(platform)
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" style={{ maxWidth: '430px', margin: '0 auto', left: 0, right: 0 }}>
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Sheet */}
      <div className="relative w-full bg-vygo-bg border-t border-vygo-border rounded-t-3xl shadow-sheet animate-slide-up pb-safe">
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-vygo-border" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-vygo-border">
          <div>
            <h2 className="text-base font-bold text-vygo-white">Tus plataformas</h2>
            <p className="text-xs text-vygo-secondary mt-0.5">
              {loading ? 'Cargando…' : `${connections.length} conectada${connections.length !== 1 ? 's' : ''}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-xl bg-vygo-card border border-vygo-border text-vygo-secondary"
          >
            <X size={16} />
          </button>
        </div>

        <div className="px-4 py-4 flex flex-col gap-3">
          {error && (
            <div className="bg-vygo-danger/10 border border-vygo-danger/30 rounded-xl px-3 py-2">
              <p className="text-xs text-vygo-danger">{error}</p>
            </div>
          )}

          {PLATFORMS.map(({ id, label, bg, color }) => {
            const connected = isConnected(id)
            const conn = getConnection(id)
            const isExpanded = expandedId === id
            const isSaving = saving === id

            return (
              <div
                key={id}
                className="bg-vygo-card border border-vygo-border rounded-2xl overflow-hidden"
              >
                {/* Platform row */}
                <div className="flex items-center gap-3 px-4 py-3.5">
                  {/* Logo pill */}
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-xs font-bold"
                    style={{ background: bg, color }}
                  >
                    {id === 'uber'  && 'UE'}
                    {id === 'rappi' && 'R'}
                    {id === 'didi'  && 'DD'}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-vygo-white">{label}</p>
                    {connected && conn?.driver_alias && (
                      <p className="text-xs text-vygo-secondary truncate">@{conn.driver_alias}</p>
                    )}
                    {connected && !conn?.driver_alias && (
                      <p className="text-xs text-vygo-green">Conectada</p>
                    )}
                    {!connected && (
                      <p className="text-xs text-vygo-secondary">No conectada</p>
                    )}
                  </div>

                  {/* Action */}
                  {isSaving ? (
                    <Loader2 size={18} className="text-vygo-secondary animate-spin" />
                  ) : connected ? (
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 bg-vygo-green/10 border border-vygo-green/20 rounded-full px-2 py-1">
                        <Check size={11} className="text-vygo-green" />
                        <span className="text-[10px] text-vygo-green font-semibold">Activa</span>
                      </div>
                      <button
                        onClick={() => handleDisconnect(id)}
                        className="w-8 h-8 flex items-center justify-center rounded-xl bg-vygo-danger/10 border border-vygo-danger/20 text-vygo-danger"
                      >
                        <Unplug size={13} />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : id)}
                      className="flex items-center gap-1 text-xs font-semibold text-vygo-green hover:text-vygo-green/80 transition-colors"
                    >
                      Conectar <ChevronRight size={13} className={isExpanded ? 'rotate-90 transition-transform' : 'transition-transform'} />
                    </button>
                  )}
                </div>

                {/* Expand: connect form */}
                {isExpanded && !connected && (
                  <div className="px-4 pb-4 border-t border-vygo-border pt-3 flex flex-col gap-3">
                    <p className="text-xs text-vygo-secondary leading-relaxed">
                      Ingresa tu alias en {label} (opcional) — solo para mostrar en tu perfil.
                    </p>
                    <input
                      type="text"
                      placeholder={`Tu alias en ${label}`}
                      value={alias}
                      onChange={(e) => setAlias(e.target.value)}
                      className="w-full bg-vygo-bg border border-vygo-border rounded-xl px-3 py-2.5 text-sm text-vygo-white placeholder:text-vygo-secondary/50 focus:outline-none focus:border-vygo-green/50"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setExpandedId(null); setAlias('') }}
                        className="flex-1 h-10 rounded-xl border border-vygo-border text-vygo-secondary text-sm"
                      >
                        Cancelar
                      </button>
                      <Button
                        onClick={() => handleConnect(id)}
                        disabled={isSaving}
                        className="flex-1 h-10"
                      >
                        {isSaving ? <Loader2 size={14} className="animate-spin" /> : 'Conectar'}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}

          <p className="text-center text-[10px] text-vygo-secondary/40 px-4 pb-2 leading-relaxed">
            Las plataformas no comparten datos con VYGO. Solo registramos que las usas para personalizar tu experiencia.
          </p>
        </div>
      </div>
    </div>
  )
}
