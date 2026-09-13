/**
 * MapRouteController
 * Controlador oficial de navegación en tiempo real con MapLibre GL y Turf.js.
 * Cumple estrictamente con la especificación de la Parte C:
 *   - Estado: plan, tramos, indice, pos
 *   - Tres métodos públicos: setPlan(plan, pos), onPosicion(pos), avanzar()
 *   - Capas: pendiente, recorrida, borde blanco, activa (todas con tolerance: 0)
 *   - Recorte local en navegador con nearestPointOnLine y lineSlice sin llamadas de red por tick
 *   - Reglas de re-ruteo: restanteM < 40 en 2 lecturas seguidas, desvíoM > 60 en 3 lecturas seguidas
 */

import {
  Map as MLMap,
  Marker,
  type GeoJSONSource,
} from 'maplibre-gl'
import nearestPointOnLine from '@turf/nearest-point-on-line'
import lineSlice from '@turf/line-slice'
import { point, lineString, featureCollection } from '@turf/helpers'

export interface Parada {
  id: string
  pedidoId: string
  tipo: 'P' | 'D'
  lat: number
  lon: number
}

export interface Tramo {
  de: string
  a: string
  segundos: number
  metros: number
  geometria: {
    type: 'LineString'
    coordinates: [number, number][]
  }
  resuelto: boolean
}

export interface RutaApiResponse {
  tramos: Tramo[]
  totales: {
    metros: number
    segundos: number
  }
  diagnostico: {
    ms: number
    tramos_sin_resolver: number
  }
}

export interface MapRouteControllerOptions {
  onAdvance?: (nuevoIndice: number) => void
  onMetricsUpdate?: (m: { restanteM: number; desvioM: number }) => void
  apiBaseUrl?: string
}

function haversineMetros(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const R = 6371000
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(Math.min(1.0, a)))
}

export class MapRouteController {
  // Estado requerido
  public plan: Parada[] = []
  public tramos: Tramo[] = []
  public indice: number = 0
  public pos: { lat: number; lon: number } = { lat: 25.6714, lon: -100.3094 }

  // Variables privadas de control y mapa
  private map: MLMap | null = null
  private driverMarker: Marker | null = null
  private stopMarkers: Marker[] = []
  private contadorLlegada: number = 0
  private contadorDesvio: number = 0
  private isPidiendoRuta: boolean = false
  private options: MapRouteControllerOptions

  constructor(map: MLMap, options?: MapRouteControllerOptions) {
    this.map = map
    this.options = options ?? {}

    if (map.loaded()) {
      this.initLayers()
    } else {
      map.once('load', () => this.initLayers())
    }
  }

  // ── Inicialización de capas una sola vez ──────────────────────────────
  private initLayers(): void {
    if (!this.map) return

    // Eliminar si ya existieran por recarga en caliente
    const layerIds = [
      'route-conector-gps',
      'route-activa-line',
      'route-activa-casing',
      'route-recorrida',
      'route-pendiente',
    ]
    layerIds.forEach((id) => {
      if (this.map!.getLayer(id)) this.map!.removeLayer(id)
    })
    const sourceIds = [
      'route-conector-gps',
      'route-activa',
      'route-recorrida',
      'route-pendiente',
    ]
    sourceIds.forEach((id) => {
      if (this.map!.getSource(id)) this.map!.removeSource(id)
    })

    // 1. Fuente y Capa: Pendiente (resto del plan) — azul punteada
    this.map.addSource('route-pendiente', {
      type: 'geojson',
      tolerance: 0,
      data: { type: 'FeatureCollection', features: [] },
    })
    this.map.addLayer({
      id: 'route-pendiente',
      type: 'line',
      source: 'route-pendiente',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#4B51A3',
        'line-width': 4,
        'line-opacity': 0.3,
        'line-dasharray': [2, 2],
      },
    })

    // 2. Fuente y Capa: Recorrida (lo ya recorrido del tramo) — gris
    this.map.addSource('route-recorrida', {
      type: 'geojson',
      tolerance: 0,
      data: { type: 'FeatureCollection', features: [] },
    })
    this.map.addLayer({
      id: 'route-recorrida',
      type: 'line',
      source: 'route-recorrida',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#A8A396',
        'line-width': 5,
        'line-opacity': 0.55,
      },
    })

    // 3. Fuente y Capas: Activa (borde blanco casing 9px + línea verde 6px)
    this.map.addSource('route-activa', {
      type: 'geojson',
      tolerance: 0,
      data: { type: 'FeatureCollection', features: [] },
    })
    this.map.addLayer({
      id: 'route-activa-casing',
      type: 'line',
      source: 'route-activa',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#FFFFFF',
        'line-width': 9,
        'line-opacity': 0.95,
      },
    })
    this.map.addLayer({
      id: 'route-activa-line',
      type: 'line',
      source: 'route-activa',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#6FA800',
        'line-width': 6,
      },
    })

    // 4. Fuente y Capa: Conector punteado si el GPS dista > 30m del inicio vial
    this.map.addSource('route-conector-gps', {
      type: 'geojson',
      tolerance: 0,
      data: { type: 'FeatureCollection', features: [] },
    })
    this.map.addLayer({
      id: 'route-conector-gps',
      type: 'line',
      source: 'route-conector-gps',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#1E88E5',
        'line-width': 2.5,
        'line-dasharray': [1.5, 2],
        'line-opacity': 0.75,
      },
    })

    // Actualizar marcadores iniciales si ya existían datos
    this.renderMarkers()
    this.actualizarCapasVisuales()
  }

  // ── Llamada HTTP única a POST /ruta ──────────────────────────────────
  private async pedirRuta(pos: { lat: number; lon: number }): Promise<void> {
    if (this.indice >= this.plan.length) {
      this.tramos = []
      this.limpiarCapas()
      return
    }

    if (this.isPidiendoRuta) return
    this.isPidiendoRuta = true

    const paradasRestantes = this.plan.slice(this.indice)
    const payload = {
      origen: { lat: pos.lat, lon: pos.lon },
      destinos: paradasRestantes.map((p) => ({ id: p.id, lat: p.lat, lon: p.lon })),
    }

    const baseUrls = [
      this.options.apiBaseUrl,
      import.meta.env.VITE_AGENT_URL,
      'http://localhost:8000',
      'https://vygo-backend.onrender.com',
    ].filter(Boolean) as string[]

    // Eliminar duplicados preservando orden de prioridad
    const uniqueUrls = Array.from(new Set(baseUrls))
    let data: RutaApiResponse | null = null

    for (const baseUrl of uniqueUrls) {
      try {
        const url = `${baseUrl.replace(/\/$/, '')}/ruta`
        const res = await Promise.race([
          fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          }),
          new Promise<Response>((_, reject) =>
            setTimeout(() => reject(new Error('timeout')), 5000)
          ),
        ])

        if (res.ok) {
          data = await res.json()
          break
        }
      } catch (err) {
        // Intentar siguiente URL
      }
    }

    this.isPidiendoRuta = false

    if (data && data.tramos && data.tramos.length > 0) {
      this.tramos = data.tramos
    } else {
      console.error('[MapRouteController] Error en /ruta; aplicando fallback en línea recta')
      const target = paradasRestantes[0]
      const distM = haversineMetros(pos.lon, pos.lat, target.lon, target.lat)
      const fallbackTramo: Tramo = {
        de: 'origen',
        a: target.id,
        metros: Math.round(distM),
        segundos: Math.round(distM / (25.0 / 3.6)),
        geometria: {
          type: 'LineString',
          coordinates: [
            [pos.lon, pos.lat],
            [target.lon, target.lat],
          ],
        },
        resuelto: false,
      }
      this.tramos = [fallbackTramo]
    }

    this.renderMarkers()
    this.actualizarCapasVisuales()
  }

  // ── Actualización de fuentes GeoJSON de MapLibre ───────────────────────
  private actualizarCapasVisuales(activaCoords?: [number, number][], recorridaCoords?: [number, number][]): void {
    if (!this.map || !this.map.loaded()) return

    const srcActiva = this.map.getSource('route-activa') as GeoJSONSource | undefined
    const srcRecorrida = this.map.getSource('route-recorrida') as GeoJSONSource | undefined
    const srcPendiente = this.map.getSource('route-pendiente') as GeoJSONSource | undefined
    const srcConector = this.map.getSource('route-conector-gps') as GeoJSONSource | undefined

    if (!srcActiva || !srcRecorrida || !srcPendiente || !srcConector) return

    if (!this.tramos || this.tramos.length === 0) {
      this.limpiarCapas()
      return
    }

    const tramoActivo = this.tramos[0]
    const coordsActivas = activaCoords ?? tramoActivo.geometria.coordinates

    // 1. Capa activa
    srcActiva.setData({
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: coordsActivas,
      },
      properties: { resuelto: tramoActivo.resuelto },
    })

    // Si resuelto es false, pintar con line-dasharray [1, 2]
    try {
      if (this.map.getLayer('route-activa-line')) {
        this.map.setPaintProperty(
          'route-activa-line',
          'line-dasharray',
          tramoActivo.resuelto ? [1, 0] : [1, 2]
        )
      }
    } catch {}

    // 2. Capa recorrida
    if (recorridaCoords && recorridaCoords.length >= 2) {
      srcRecorrida.setData({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: recorridaCoords,
        },
        properties: {},
      })
    } else {
      srcRecorrida.setData({ type: 'FeatureCollection', features: [] })
    }

    // 3. Capa pendiente (resto del plan: tramos 1..N)
    const pendientes = this.tramos.slice(1)
    if (pendientes.length > 0) {
      const features = pendientes.map((t) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'LineString' as const,
          coordinates: t.geometria.coordinates,
        },
        properties: { de: t.de, a: t.a },
      }))
      srcPendiente.setData({ type: 'FeatureCollection', features })
    } else {
      srcPendiente.setData({ type: 'FeatureCollection', features: [] })
    }

    // 4. Conector GPS punteado si dist > 30 m del inicio de la línea
    if (coordsActivas.length >= 1) {
      const inicioLinea = coordsActivas[0]
      const distM = haversineMetros(this.pos.lon, this.pos.lat, inicioLinea[0], inicioLinea[1])
      if (distM > 30.0) {
        srcConector.setData({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [
              [this.pos.lon, this.pos.lat],
              [inicioLinea[0], inicioLinea[1]],
            ],
          },
          properties: {},
        })
      } else {
        srcConector.setData({ type: 'FeatureCollection', features: [] })
      }
    }
  }

  private limpiarCapas(): void {
    if (!this.map || !this.map.loaded()) return
    const ids = ['route-activa', 'route-recorrida', 'route-pendiente', 'route-conector-gps']
    ids.forEach((id) => {
      const src = this.map!.getSource(id) as GeoJSONSource | undefined
      if (src) src.setData({ type: 'FeatureCollection', features: [] })
    })
  }

  // ── Renderizado de Marcadores de Paradas y Repartidor ─────────────────
  private renderMarkers(): void {
    const map = this.map
    if (!map) return

    // Limpiar marcadores viejos de paradas
    this.stopMarkers.forEach((m) => m.remove())
    this.stopMarkers = []

    this.plan.forEach((parada, idx) => {
      if (idx < this.indice) return // Omitir paradas ya superadas

      const isNext = idx === this.indice
      const num = String(idx + 1)
      const el = document.createElement('div')
      el.style.cssText = `cursor: pointer; transform: scale(${isNext ? 1.0 : 0.72}); opacity: ${isNext ? 1.0 : 0.75}; transition: transform 0.2s ease, opacity 0.2s ease;`

      if (parada.tipo === 'P') {
        // Recoger -> círculo naranja #C1610A relleno, número blanco, borde blanco 3 px
        el.innerHTML = `
          <div style="width: 32px; height: 32px; background: #C1610A; border: 3px solid #FFFFFF; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-family: Inter, sans-serif; font-weight: 800; font-size: 13px; color: #FFFFFF; box-shadow: 0 2px 10px rgba(193, 97, 10, 0.45);">
            ${num}
          </div>
        `
      } else {
        // Entregar -> círculo blanco, anillo verde #6FA800 de 4 px, número verde
        el.innerHTML = `
          <div style="width: 32px; height: 32px; background: #FFFFFF; border: 4px solid #6FA800; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-family: Inter, sans-serif; font-weight: 800; font-size: 13px; color: #6FA800; box-shadow: 0 2px 10px rgba(111, 168, 0, 0.45);">
            ${num}
          </div>
        `
      }

      const marker = new Marker({ element: el, anchor: 'center' })
        .setLngLat([parada.lon, parada.lat])
        .addTo(map)
      this.stopMarkers.push(marker)
    })

    // Marcador del repartidor: punto azul #1E88E5 con borde blanco y halo
    if (!this.driverMarker) {
      const driverEl = document.createElement('div')
      driverEl.style.cssText =
        'width: 36px; height: 36px; position: relative; display: flex; align-items: center; justify-content: center;'
      driverEl.innerHTML = `
        <div style="position: absolute; inset: 0; background: #1E88E5; border-radius: 50%; opacity: 0.25; animation: ping 2.5s cubic-bezier(0,0,0.2,1) infinite;"></div>
        <div style="position: absolute; inset: 5px; background: #1E88E5; border-radius: 50%; opacity: 0.2;"></div>
        <div style="position: relative; width: 20px; height: 20px; background: #1E88E5; border-radius: 50%; border: 3px solid #FFFFFF; box-shadow: 0 2px 10px rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center;">
          <div style="width: 5px; height: 5px; background: #FFFFFF; border-radius: 50%;"></div>
        </div>
      `
      this.driverMarker = new Marker({ element: driverEl, anchor: 'center' })
        .setLngLat([this.pos.lon, this.pos.lat])
        .addTo(map)
    } else {
      this.driverMarker.setLngLat([this.pos.lon, this.pos.lat])
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  // TRES MÉTODOS PÚBLICOS
  // ══════════════════════════════════════════════════════════════════════

  /**
   * 1. setPlan(plan, pos)
   * El agente devolvió un plan nuevo. Descarta TODOS los tramos,
   * pone índice en 0 y pide /ruta.
   */
  public async setPlan(plan: Parada[], pos: { lat: number; lon: number }): Promise<void> {
    this.plan = plan
    this.tramos = []
    this.indice = 0
    this.pos = pos
    this.contadorLlegada = 0
    this.contadorDesvio = 0

    if (this.driverMarker) {
      this.driverMarker.setLngLat([pos.lon, pos.lat])
    }

    await this.pedirRuta(pos)
  }

  /**
   * 2. onPosicion(pos)
   * Cada lectura del GPS. NO llama al servidor.
   * Proyecta localmente con Turf sobre tramos[0].geometria:
   *   - lineSlice(sobre, fin, linea)  -> lo que falta  (capa activa)
   *   - lineSlice(ini, sobre, linea)  -> lo recorrido
   *   - desvioM   = sobre.properties.dist * 1000
   *   - restanteM = tramos[0].metros - sobre.properties.location * 1000
   */
  public onPosicion(pos: { lat: number; lon: number }): void {
    this.pos = pos
    if (this.driverMarker) {
      this.driverMarker.setLngLat([pos.lon, pos.lat])
    }

    if (!this.tramos || this.tramos.length === 0 || !this.tramos[0]?.geometria) {
      return
    }

    const tramoActivo = this.tramos[0]
    const coords = tramoActivo.geometria.coordinates
    if (!coords || coords.length < 2) return

    try {
      const linea = lineString(coords)
      const pt = point([pos.lon, pos.lat])
      const sobre = nearestPointOnLine(linea, pt)

      const distKm = sobre.properties?.dist ?? 0
      const locationKm = sobre.properties?.location ?? 0

      const desvioM = distKm * 1000.0
      const restanteM = tramoActivo.metros - locationKm * 1000.0

      if (this.options.onMetricsUpdate) {
        this.options.onMetricsUpdate({ restanteM: Math.max(0, restanteM), desvioM })
      }

      // Proyección y recorte local envuelto en try/catch por colisiones en vértices
      const ini = point(coords[0])
      const fin = point(coords[coords.length - 1])

      let activaCoords: [number, number][] = coords
      let recorridaCoords: [number, number][] = []

      try {
        const faltaSlice = lineSlice(sobre, fin, linea)
        if (faltaSlice.geometry.coordinates.length >= 2) {
          activaCoords = faltaSlice.geometry.coordinates as [number, number][]
        }
      } catch (e) {
        // Mantener activaCoords si la proyección colisiona exactamente con un vértice
      }

      try {
        const recorridaSlice = lineSlice(ini, sobre, linea)
        if (recorridaSlice.geometry.coordinates.length >= 2) {
          recorridaCoords = recorridaSlice.geometry.coordinates as [number, number][]
        }
      } catch (e) {
        // Silencioso
      }

      this.actualizarCapasVisuales(activaCoords, recorridaCoords)

      // Regla (a): restanteM < 40 en 2 lecturas SEGUIDAS -> avanzar()
      if (restanteM < 40.0) {
        this.contadorLlegada++
        if (this.contadorLlegada >= 2) {
          this.contadorLlegada = 0
          this.avanzar()
          return
        }
      } else {
        this.contadorLlegada = 0
      }

      // Regla (b): desvioM > 60 en 3 lecturas SEGUIDAS (~6 s) -> re-rutea al mismo destino
      if (desvioM > 60.0) {
        this.contadorDesvio++
        if (this.contadorDesvio >= 3) {
          this.contadorDesvio = 0
          this.pedirRuta(pos)
          return
        }
      } else {
        this.contadorDesvio = 0
      }
    } catch (err) {
      console.warn('[MapRouteController] Error en onPosicion:', err)
    }
  }

  /**
   * 3. avanzar()
   * El repartidor confirmó la parada. indice++, y vuelve a pedir /ruta con origen = LA POSICION ACTUAL.
   * Aquí es donde la línea se re-ancla en el repartidor. Si ya no quedan paradas, limpia.
   */
  public async avanzar(): Promise<void> {
    this.indice++
    this.contadorLlegada = 0
    this.contadorDesvio = 0

    if (this.options.onAdvance) {
      this.options.onAdvance(this.indice)
    }

    if (this.indice >= this.plan.length) {
      this.tramos = []
      this.limpiarCapas()
      this.renderMarkers()
      return
    }

    await this.pedirRuta(this.pos)
  }

  public destroy(): void {
    if (this.driverMarker) {
      this.driverMarker.remove()
      this.driverMarker = null
    }
    this.stopMarkers.forEach((m) => m.remove())
    this.stopMarkers = []
    this.map = null
  }
}
