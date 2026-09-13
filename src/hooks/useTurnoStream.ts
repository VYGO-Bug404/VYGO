import { useState, useEffect, useRef, useCallback } from 'react'
import type { Frame, Telemetria } from '@/lib/vygoAgent'

const AGENT_URL = import.meta.env.VITE_AGENT_URL || 'https://vygo-backend.onrender.com'

interface UseTurnoStreamOptions {
  escenario?: number
  politica?: 'agente_ppo' | 'B2_umbral' | 'B1_simple'
  velocidad?: number
  autoStart?: boolean
}

interface StreamState {
  running: boolean
  t: number            // tiempo de simulación en segundos
  telemetria: Telemetria | null
  lastFrame: Frame | null
  error: string | null
  driverPos: { lat: number; lon: number } | null
  routeCoords: [number, number][] | null
}

export function useTurnoStream({
  escenario = 12,
  politica = 'agente_ppo',
  velocidad = 10,
  autoStart = false,
}: UseTurnoStreamOptions = {}) {
  const [state, setState] = useState<StreamState>({
    running: false,
    t: 0,
    telemetria: null,
    lastFrame: null,
    error: null,
    driverPos: null,
    routeCoords: null,
  })

  const esRef = useRef<EventSource | null>(null)

  const stop = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setState((s) => ({ ...s, running: false }))
  }, [])

  const start = useCallback(() => {
    if (!AGENT_URL) {
      setState((s) => ({ ...s, error: 'VITE_AGENT_URL no configurada' }))
      return
    }
    if (esRef.current) stop()

    const url = `${AGENT_URL}/turno/stream?escenario=${escenario}&politica=${politica}&velocidad=${velocidad}`
    const es = new EventSource(url)
    esRef.current = es

    setState((s) => ({ ...s, running: true, error: null, t: 0 }))

    es.onmessage = (e) => {
      try {
        const frame: Frame = JSON.parse(e.data)

        setState((s) => {
          const next: Partial<StreamState> = { lastFrame: frame, t: frame.t }

          if (frame.tipo === 'posicion') {
            next.driverPos = { lat: frame.pos.lat, lon: frame.pos.lon }
          }
          if (frame.tipo === 'replan') {
            next.routeCoords = frame.plan.geometria.coordinates
          }
          if (frame.tipo === 'telemetria') {
            next.telemetria = frame.telemetria
          }
          if (frame.tipo === 'fin') {
            next.running = false
            es.close()
          }

          return { ...s, ...next }
        })
      } catch {
        // frame malformado, ignorar
      }
    }

    es.onerror = () => {
      setState((s) => ({ ...s, running: false, error: 'Error en el stream SSE' }))
      es.close()
    }
  }, [escenario, politica, velocidad, stop])

  useEffect(() => {
    if (autoStart) start()
    return stop
  }, [autoStart, start, stop])

  return { ...state, start, stop }
}
