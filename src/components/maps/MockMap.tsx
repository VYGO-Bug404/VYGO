import { useRef, useEffect, useState } from 'react'
import {
  Map as MLMap,
  AttributionControl,
  NavigationControl,
  LngLatBounds,
  type StyleSpecification,
} from 'maplibre-gl'
import { cn } from '@/lib/utils'
import type { Order } from '@/types/order'
import {
  MapRouteController,
  type Parada,
} from '@/lib/mapRouteController'

export interface RouteGeoJSON {
  type: 'LineString'
  coordinates: [number, number][]
}

export interface MockMapProps {
  activeOrders?: Order[]
  routeGeoJSON?: RouteGeoJSON | null
  className?: string
  showFullRoute?: boolean
  followDriver?: boolean
  fitToRoute?: boolean
  controllerRef?: React.MutableRefObject<MapRouteController | null>
  onAdvance?: (index: number) => void
  onMetricsUpdate?: (m: { restanteM: number; desvioM: number }) => void
}

const MONTERREY: [number, number] = [-100.3161, 25.6866]
const LOCATION_KEY = 'vygo-last-position'

function getSavedPosition(): [number, number] {
  try {
    const raw = localStorage.getItem(LOCATION_KEY)
    if (!raw) return MONTERREY
    const { lng, lat } = JSON.parse(raw)
    if (typeof lat === 'number' && typeof lng === 'number') return [lng, lat]
  } catch {}
  return MONTERREY
}

function savePosition(lng: number, lat: number) {
  try {
    localStorage.setItem(LOCATION_KEY, JSON.stringify({ lng, lat, lon: lng }))
  } catch {}
}

const KEY = import.meta.env.VITE_MAPTILER_KEY || 'YCKX2ukadzz48kPBnfcK'

function buildStyle(): StyleSpecification {
  const tiles = KEY
    ? [`https://api.maptiler.com/maps/dataviz/{z}/{x}/{y}.png?key=${KEY}`]
    : [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      ]

  return {
    version: 8,
    sources: {
      basemap: {
        type: 'raster',
        tiles,
        tileSize: 256,
        attribution: KEY
          ? '© MapTiler © OpenStreetMap contributors'
          : '© Esri © OpenStreetMap contributors',
        maxzoom: KEY ? 22 : 16,
      },
    },
    layers: [{ id: 'basemap', type: 'raster', source: 'basemap' }],
  }
}

export function ordersToParadas(orders: Order[]): Parada[] {
  const paradas: Parada[] = []
  orders.forEach((o, idx) => {
    if (o.status !== 'picked_up' && o.status !== 'delivered') {
      paradas.push({
        id: `P-${o.id}-${idx}`,
        pedidoId: o.id,
        tipo: 'P',
        lat: o.pickup.lat,
        lon: o.pickup.lng,
      })
    }
  })
  orders.forEach((o, idx) => {
    if (o.status !== 'delivered') {
      paradas.push({
        id: `D-${o.id}-${idx}`,
        pedidoId: o.id,
        tipo: 'D',
        lat: o.dropoff.lat,
        lon: o.dropoff.lng,
      })
    }
  })
  return paradas
}

export function MockMap({
  activeOrders = [],
  routeGeoJSON,
  className,
  showFullRoute = false,
  followDriver = false,
  fitToRoute = false,
  controllerRef: externalControllerRef,
  onAdvance,
  onMetricsUpdate,
}: MockMapProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MLMap | null>(null)
  const controllerRef = useRef<MapRouteController | null>(null)
  const watchRef = useRef<number | null>(null)
  const followDriverRef = useRef(followDriver)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    followDriverRef.current = followDriver
  }, [followDriver])

  // ── Inicialización del Mapa ──────────────────────────────
  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap || mapRef.current) return

    let raf: number
    let map: MLMap | null = null

    const init = () => {
      if (mapRef.current) return
      try {
        map = new MLMap({
          container: wrap,
          style: buildStyle(),
          center: getSavedPosition(),
          zoom: 15,
          attributionControl: false,
        })

        map.addControl(new AttributionControl({ compact: true }), 'bottom-left')
        map.addControl(new NavigationControl({ showCompass: false }), 'bottom-right')

        map.on('error', (e) => {
          console.error('[VYGO Map]', e.error)
          setError(e.error?.message ?? 'Error cargando el mapa')
        })

        map.on('load', () => {
          map!.resize()
          // Crear controlador MapRouteController
          const ctrl = new MapRouteController(map!, {
            onAdvance,
            onMetricsUpdate,
          })
          controllerRef.current = ctrl
          if (externalControllerRef) {
            externalControllerRef.current = ctrl
          }
          setReady(true)
        })

        mapRef.current = map
      } catch (err) {
        console.error('[VYGO Map init]', err)
        setError(String(err))
      }
    }

    raf = requestAnimationFrame(init)

    return () => {
      cancelAnimationFrame(raf)
      controllerRef.current?.destroy()
      controllerRef.current = null
      if (externalControllerRef) externalControllerRef.current = null
      map?.remove()
      mapRef.current = null
      setReady(false)
      setError(null)
    }
  }, [])

  // ── Sincronizar Plan del Agente al Controlador ───────────
  useEffect(() => {
    const ctrl = controllerRef.current
    if (!ctrl || !ready) return

    const [savedLng, savedLat] = getSavedPosition()
    const currentGps = { lat: savedLat, lon: savedLng }
    const paradas = ordersToParadas(activeOrders)

    if (paradas.length > 0) {
      ctrl.setPlan(paradas, currentGps)
    }
  }, [activeOrders, ready])

  // ── Escucha de GPS Real (watchPosition) ───────────────────
  useEffect(() => {
    if (!ready || !navigator.geolocation) return

    const handleGpsUpdate = (pos: GeolocationPosition) => {
      const { longitude: lng, latitude: lat } = pos.coords
      savePosition(lng, lat)

      // 1. Enviar lectura al controlador: recorte local con Turf (sin llamadas al servidor)
      if (controllerRef.current) {
        controllerRef.current.onPosicion({ lat, lon: lng })
      }

      // 2. Centrado suave si followDriver está activo
      if (followDriverRef.current && mapRef.current) {
        mapRef.current.easeTo({ center: [lng, lat], duration: 600, essential: true })
      }
    }

    // Lectura inicial inmediata
    navigator.geolocation.getCurrentPosition(handleGpsUpdate, () => {}, {
      enableHighAccuracy: true,
      timeout: 8000,
    })

    // Monitoreo continuo
    const watchId = navigator.geolocation.watchPosition(
      handleGpsUpdate,
      () => {},
      { enableHighAccuracy: true, maximumAge: 3000 }
    )
    watchRef.current = watchId

    return () => {
      if (watchRef.current !== null) {
        navigator.geolocation.clearWatch(watchRef.current)
      }
    }
  }, [ready])

  // ── Fit Bounds inicial sobre paradas activas ──────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || (!fitToRoute && !showFullRoute) || activeOrders.length === 0) return

    const bounds = new LngLatBounds()
    bounds.extend(getSavedPosition())
    activeOrders.forEach((order) => {
      bounds.extend([order.pickup.lng, order.pickup.lat])
      bounds.extend([order.dropoff.lng, order.dropoff.lat])
    })

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 80, duration: 600, maxZoom: 15 })
    }
  }, [activeOrders, ready, fitToRoute, showFullRoute])

  return (
    <div className={cn('relative overflow-hidden bg-[#dde3f0]', className)}>
      <div ref={wrapRef} className="w-full h-full" />

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-vygo-bg/90 z-10">
          <div className="text-center px-6">
            <p className="text-vygo-danger text-sm font-semibold mb-1">Error al cargar mapa</p>
            <p className="text-vygo-secondary text-xs">{error}</p>
          </div>
        </div>
      )}

      {!KEY && !error && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-10 pointer-events-none whitespace-nowrap">
          <div className="bg-white/80 backdrop-blur-sm text-vygo-secondary text-[10px] px-3 py-1.5 rounded-full border border-vygo-border">
            Agrega <code className="text-vygo-warning">VITE_MAPTILER_KEY</code> para mapa vectorial
          </div>
        </div>
      )}
    </div>
  )
}
