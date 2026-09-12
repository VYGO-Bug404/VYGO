interface EndShiftConfirmProps {
  activeCount: number
  onConfirm: () => void
  onCancel: () => void
}

export function EndShiftConfirm({ activeCount, onConfirm, onCancel }: EndShiftConfirmProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative w-full max-w-[430px] bg-vygo-card border-t border-vygo-border rounded-t-3xl px-5 pt-5 pb-8 shadow-sheet"
        style={{ paddingBottom: `calc(2rem + env(safe-area-inset-bottom, 0px))` }}>
        <div className="w-10 h-1 rounded-full bg-vygo-border mx-auto mb-5" />
        <h3 className="text-base font-bold text-vygo-white mb-1">¿Terminar jornada?</h3>
        <p className="text-sm text-vygo-secondary mb-5">
          Tienes <span className="text-vygo-warning font-semibold">{activeCount} {activeCount === 1 ? 'pedido activo' : 'pedidos activos'}</span>. Al terminar la jornada se cancelarán.
        </p>
        <div className="flex flex-col gap-2">
          <button
            onClick={onConfirm}
            className="w-full h-12 rounded-2xl bg-vygo-danger text-white text-sm font-semibold hover:bg-vygo-danger/90 transition-colors"
          >
            Sí, terminar jornada
          </button>
          <button
            onClick={onCancel}
            className="w-full h-12 rounded-2xl border border-vygo-border text-vygo-secondary text-sm font-medium hover:text-vygo-white transition-colors"
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  )
}
