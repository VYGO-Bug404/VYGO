import { supabase } from '@/lib/supabase'

export interface AppConfig {
  maxPedidosSimultaneos: number
  expiracionOfertaSeg: number
}

const _config: AppConfig = {
  maxPedidosSimultaneos: 3,
  expiracionOfertaSeg: 30,
}

export async function loadConfig(): Promise<void> {
  const { data } = await supabase.from('configuracion').select('clave, valor')
  if (!data) return
  const map = Object.fromEntries(data.map((r: { clave: string; valor: string }) => [r.clave, r.valor]))
  if (map['max_pedidos_simultaneos']) _config.maxPedidosSimultaneos = parseInt(map['max_pedidos_simultaneos'], 10)
  if (map['expiracion_oferta_seg']) _config.expiracionOfertaSeg = parseInt(map['expiracion_oferta_seg'], 10)
}

export function getConfig(): AppConfig {
  return _config
}
