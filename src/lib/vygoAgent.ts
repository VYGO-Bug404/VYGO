// ─── Tipos del contrato de integración VYGO v1.0 ───────────────────────────
// Fuente de verdad: VYGO-contrato-integracion-agente.pdf

export type Punto = { lat: number; lon: number }
export type Politica = 'agente_ppo' | 'agente_bc' | 'B2_umbral' | 'B1_simple'
export type Decision = 'aceptar' | 'rechazar'
export type TipoParada = 'recoleccion' | 'entrega'
export type EstadoParada = 'pendiente' | 'en_curso' | 'completada'
export type MotivoInfactible =
  | 'capacidad' | 'frescura' | 'fecha_limite'
  | 'expirada' | 'incompatible_plataforma' | 'fuera_de_turno'

export interface Economia {
  tarifa_mxn: number
  delta_tiempo_min: number
  delta_distancia_km: number
  costo_marginal_mxn: number
  ganancia_neta_mxn: number
  tasa_marginal_mxn_h: number
  rho_actual_mxn_h: number
  ajuste_aprendido_mxn_h: number
  umbral_superado: boolean
}

export interface Riesgo {
  holgura_frescura_min: number
  holgura_limite_min: number
  prob_entrega_a_tiempo: number
  p_gana: number
  anillo: 1 | 2 | 3
}

export interface DecisionOferta {
  oferta_id: string
  pedido_id: string
  app: 'uber' | 'didi' | 'rappi'
  decision: Decision
  prioridad: number
  confianza: number
  economia: Economia
  riesgo: Riesgo
  factible: boolean
  motivo_infactible: MotivoInfactible | null
  explicacion_corta: string
  explicacion: string
}

export interface Parada {
  orden: number
  tipo: TipoParada
  pedido_id: string
  app: string
  punto: Punto
  direccion?: string
  eta: string
  eta_min: number
  espera_estimada_min?: number
  holgura_frescura_min: number | null
  estado: EstadoParada
}

export interface Plan {
  viaje_id: string
  paradas: Parada[]
  geometria: { type: 'LineString'; coordinates: [number, number][] } // [lon, lat] GeoJSON
  resumen: {
    paradas_totales: number
    pedidos_a_bordo: number
    distancia_km: number
    duracion_min: number
    ingreso_mxn: number
    costo_mxn: number
    tasa_proyectada_mxn_h: number
    optimo_exacto: boolean
    secuencias_evaluadas: number
  }
}

export interface Telemetria {
  rho_actual_mxn_h: number
  ganancia_turno_mxn: number
  pedidos_entregados: number
  puntualidad: number
  km_por_pedido: number
  factor_agrupamiento: number
  utilizacion: number
}

export interface Alerta {
  nivel: 'info' | 'aviso' | 'critico'
  codigo: string
  pedido_id?: string
  mensaje: string
}

export interface EventoActivo {
  tipo: 'surge' | 'cierre_vial'
  zona: string
  multiplicador_tarifa?: number
  inicia_en: string
  termina_en: string
}

export interface RespuestaDecidir {
  version: string
  generado_en: string
  politica: Politica
  latencia_ms: number
  decisiones: DecisionOferta[]
  plan: Plan
  telemetria: Telemetria
  alertas: Alerta[]
  evento_activo: EventoActivo | null
}

// ─── Tipos de frames SSE (Superficie B) ─────────────────────────────────────

export type Frame =
  | { t: number; tipo: 'inicio'; escenario: number; politica: Politica; duracion_seg: number; bbox: Record<string, number>; comercios: unknown[] }
  | { t: number; tipo: 'posicion'; pos: Punto; velocidad_kmh: number; rumbo: number }
  | { t: number; tipo: 'oferta_nueva'; oferta: unknown; anillo: 1 | 2 | 3; expira_en_seg: number }
  | { t: number; tipo: 'decision'; oferta_id: string; decision: Decision; economia: Partial<Economia>; explicacion_corta: string }
  | { t: number; tipo: 'oferta_perdida'; oferta_id: string; gano_anillo: number }
  | { t: number; tipo: 'replan'; plan: Plan }
  | { t: number; tipo: 'recoleccion'; pedido_id: string; espera_real_min: number }
  | { t: number; tipo: 'entrega'; pedido_id: string; ingreso_mxn: number; acumulado_mxn: number; a_tiempo: boolean }
  | { t: number; tipo: 'evento'; evento: 'surge' | 'cierre_vial'; zona: string; multiplicador?: number; duracion_seg: number }
  | { t: number; tipo: 'telemetria'; telemetria: Telemetria }
  | { t: number; tipo: 'fin'; resumen: Record<string, number> }

// ─── Tipo del replay pareado (Superficie C) ─────────────────────────────────

export interface ReplayPareado {
  version: string
  escenario: {
    id: number
    semilla: number
    duracion_seg: number
    bbox: { min_lat: number; max_lat: number; min_lon: number; max_lon: number }
    comercios: { id: string; punto: Punto; nombre: string }[]
    evento: { t: number; tipo: string; zona: string; multiplicador: number; duracion_seg: number }
  }
  pistas: {
    politica: Politica
    etiqueta: string
    frames: Frame[]
    resumen: {
      ingreso_mxn: number
      km: number
      rho_mxn_h: number
      entregados: number
      puntualidad: number
    }
  }[]
}
