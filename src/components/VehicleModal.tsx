import { useState } from 'react'
import { X, Bike, Car, Check } from 'lucide-react'
import { useDriverStore } from '@/stores/driver.store'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Vehicle } from '@/types/driver'

interface Props {
  onClose: () => void
}

export function VehicleModal({ onClose }: Props) {
  const currentVehicle = useDriverStore((s) => s.driver.vehicle)
  const setVehicle = useDriverStore((s) => s.setVehicle)

  const [type, setType] = useState<'moto' | 'car'>(
    currentVehicle.type === 'car' ? 'car' : 'moto'
  )
  const [brand, setBrand] = useState(currentVehicle.brand || '')
  const [model, setModel] = useState(currentVehicle.model || '')
  const [year, setYear] = useState(currentVehicle.year || '')
  const [error, setError] = useState<string | null>(null)
  const [savedSuccess, setSavedSuccess] = useState(false)

  const handleSave = () => {
    setError(null)
    if (!model.trim()) {
      setError('Por favor escribe el modelo de tu vehículo')
      return
    }

    const updated: Partial<Vehicle> = {
      type,
      brand: brand.trim(),
      model: model.trim(),
      year: year.trim() || undefined,
    }

    setVehicle(updated)
    setSavedSuccess(true)
    setTimeout(() => {
      onClose()
    }, 300)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center"
      style={{ maxWidth: '430px', margin: '0 auto', left: 0, right: 0 }}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Sheet */}
      <div className="relative w-full bg-vygo-bg border-t border-vygo-border rounded-t-3xl shadow-sheet animate-slide-up pb-safe max-h-[90vh] overflow-y-auto">
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-vygo-border" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-vygo-border">
          <div>
            <h2 className="text-base font-bold text-vygo-white">Vehículo de reparto</h2>
            <p className="text-xs text-vygo-secondary mt-0.5">
              Configura tu tipo de vehículo, modelo y año
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-xl bg-vygo-card border border-vygo-border text-vygo-secondary hover:text-vygo-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-4">
          {error && (
            <div className="bg-vygo-danger/10 border border-vygo-danger/30 rounded-xl px-3 py-2">
              <p className="text-xs text-vygo-danger font-medium">{error}</p>
            </div>
          )}

          {/* Vehicle Type Selection */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-vygo-secondary block mb-2">
              Tipo de vehículo
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setType('moto')}
                className={`flex flex-col items-center justify-center gap-2 p-3.5 rounded-2xl border transition-all duration-150 ${
                  type === 'moto'
                    ? 'border-vygo-green bg-vygo-green/10 text-vygo-white shadow-sm'
                    : 'border-vygo-border bg-vygo-card text-vygo-secondary hover:text-vygo-white'
                }`}
              >
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    type === 'moto'
                      ? 'bg-vygo-green/20 text-vygo-green'
                      : 'bg-vygo-card-2 text-vygo-secondary'
                  }`}
                >
                  <Bike size={22} />
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1.5">
                    <span className="text-sm font-semibold">Moto</span>
                    {type === 'moto' && <Check size={14} className="text-vygo-green" />}
                  </div>
                  <span className="text-[11px] text-vygo-secondary">Rutas ágiles</span>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setType('car')}
                className={`flex flex-col items-center justify-center gap-2 p-3.5 rounded-2xl border transition-all duration-150 ${
                  type === 'car'
                    ? 'border-vygo-green bg-vygo-green/10 text-vygo-white shadow-sm'
                    : 'border-vygo-border bg-vygo-card text-vygo-secondary hover:text-vygo-white'
                }`}
              >
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    type === 'car'
                      ? 'bg-vygo-green/20 text-vygo-green'
                      : 'bg-vygo-card-2 text-vygo-secondary'
                  }`}
                >
                  <Car size={22} />
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1.5">
                    <span className="text-sm font-semibold">Coche</span>
                    {type === 'car' && <Check size={14} className="text-vygo-green" />}
                  </div>
                  <span className="text-[11px] text-vygo-secondary">Mayor capacidad</span>
                </div>
              </button>
            </div>
          </div>

          {/* Brand & Model inputs */}
          <div className="space-y-3">
            <Input
              label="Marca"
              placeholder={type === 'moto' ? 'Ej. Italika, Honda, Yamaha' : 'Ej. Nissan, Chevrolet, Toyota'}
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
            />

            <Input
              label="Modelo"
              placeholder={type === 'moto' ? 'Ej. FT150, 125Z, Cargo 150' : 'Ej. Versa, Aveo, March'}
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />

            <Input
              label="Año"
              placeholder="Ej. 2022"
              type="text"
              inputMode="numeric"
              maxLength={4}
              value={year}
              onChange={(e) => setYear(e.target.value.replace(/\D/g, ''))}
            />
          </div>

          {/* Hint */}
          <p className="text-[11px] text-vygo-secondary/70 leading-relaxed">
            Esta información nos ayuda a calcular tiempos estimados de ruta y asignar pedidos adecuados para tu vehículo.
          </p>

          {/* Actions */}
          <div className="pt-2">
            <Button
              type="button"
              onClick={handleSave}
              className="w-full h-12 text-[15px]"
            >
              {savedSuccess ? '¡Guardado!' : 'Guardar vehículo'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
