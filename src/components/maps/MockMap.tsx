import { useRef, useEffect, useState } from 'react'
import {
  Map as MLMap,
  Marker,
  AttributionControl,
  NavigationControl,
  LngLatBounds,
  type GeoJSONSource,
  type StyleSpecification,
} from 'maplibre-gl'
import { cn } from '@/lib/utils'
import type { Order } from '@/types/order'

export interface RouteGeoJSON {
  type: 'LineString'
  coordinates: [number, number][]
}

interface MockMapProps {
  activeOrders?: Order[]
  routeGeoJSON?: RouteGeoJSON | null
  className?: string
  showFullRoute?: boolean
  followDriver?: boolean
  fitToRoute?: boolean
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
  try { localStorage.setItem(LOCATION_KEY, JSON.stringify({ lng, lat, lon: lng })) } catch {}
}

const PLATFORM_COLORS: Record<string, string> = {
  uber: '#334155',
  rappi: '#EF4444',
  didi: '#F97316',
}

const KEY = import.meta.env.VITE_MAPTILER_KEY || 'YCKX2ukadzz48kPBnfcK'

function buildStyle(): StyleSpecification {
  // Raster tiles — simpler and more reliable than fetching a style JSON
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

export function MockMap({
  activeOrders = [],
  routeGeoJSON,
  className,
  showFullRoute = false,
  followDriver = false,
  fitToRoute = false,
}: MockMapProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MLMap | null>(null)
  const markersRef = useRef<Marker[]>([])
  const driverRef = useRef<Marker | null>(null)
  const watchRef = useRef<number | null>(null)
  const followDriverRef = useRef(followDriver)
  const routeGeoJSONRef = useRef<RouteGeoJSON | null>(routeGeoJSON ?? null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Keep refs in sync with props
  useEffect(() => { followDriverRef.current = followDriver }, [followDriver])
  useEffect(() => { routeGeoJSONRef.current = routeGeoJSON ?? null }, [routeGeoJSON])

  // ── Init map ──────────────────────────────────────────────
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
          map!.addSource('route', {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          })
          map!.addLayer({
            id: 'route-shadow',
            type: 'line',
            source: 'route',
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': '#0F172A', 'line-width': 12, 'line-opacity': 0.25, 'line-blur': 2 },
          })
          map!.addLayer({
            id: 'route-casing',
            type: 'line',
            source: 'route',
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': '#FFFFFF', 'line-width': 9, 'line-opacity': 0.95 },
          })
          map!.addLayer({
            id: 'route-line',
            type: 'line',
            source: 'route',
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': '#6FA800', 'line-width': 6, 'line-opacity': 1.0 },
          })
          map!.addLayer({
            id: 'route-inner-glow',
            type: 'line',
            source: 'route',
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': '#BEF264', 'line-width': 2.5, 'line-opacity': 0.85 },
          })
          setReady(true)
        })

        mapRef.current = map
      } catch (err) {
        console.error('[VYGO Map init]', err)
        setError(String(err))
      }
    }

    // Wait one frame so CSS layout is applied before MapLibre reads dimensions
    raf = requestAnimationFrame(init)

    return () => {
      cancelAnimationFrame(raf)
      map?.remove()
      mapRef.current = null
      setReady(false)
      setError(null)
    }
  }, [])

  // ── Route line ────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const src = map.getSource('route') as GeoJSONSource | undefined
    if (!src) return

    let validFeature = false
    let activeCoords: [number, number][] = []

    if (routeGeoJSON?.coordinates && routeGeoJSON.coordinates.length >= 2) {
      activeCoords = routeGeoJSON.coordinates
      validFeature = true
    } else if (activeOrders.length > 0) {
      // Fallback inmediato para que la línea jamás desaparezca en el mapa
      const saved = getSavedPosition()
      const fallbackCoords: [number, number][] = [saved]
      activeOrders.forEach((o) => {
        if (o.status !== 'picked_up') fallbackCoords.push([o.pickup.lng, o.pickup.lat])
        fallbackCoords.push([o.dropoff.lng, o.dropoff.lat])
      })
      if (fallbackCoords.length >= 2) {
        activeCoords = fallbackCoords
        validFeature = true
      }
    }

    if (validFeature && activeCoords.length >= 2) {
      src.setData({
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: activeCoords,
            },
            properties: {},
          },
        ],
      })

      // Enmarcar cámara para que el repartidor vea el trayecto completo
      const bounds = new LngLatBounds()
      activeCoords.forEach(([lng, lat]) => bounds.extend([lng, lat]))
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 80, maxZoom: 15, duration: 800 })
      }
    } else {
      src.setData({ type: 'FeatureCollection', features: [] })
    }
  }, [routeGeoJSON, activeOrders, ready])

  // ── Pickup + Dropoff markers ──────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []

    activeOrders.forEach((order, i) => {
      const num = String(order.routeNumber ?? (i + 1))
      const isFirst = (order.routeNumber ?? (i + 1)) === 1
      const alreadyPickedUp = order.status === 'picked_up'

      // ── PICKUP marker — solo si aún no fue recogido ──
      if (!alreadyPickedUp) {
        const pickupEl = document.createElement('div')
        pickupEl.style.cssText = 'cursor:pointer;'

        if (isFirst) {
          // Círculo lima
          pickupEl.innerHTML = `
            <div style="width:34px;height:34px;background:#FFFFFF;border:2.5px solid #6FA800;
              border-radius:50%;display:flex;align-items:center;justify-content:center;
              font-family:Inter,sans-serif;font-weight:700;font-size:13px;color:#6FA800;
              box-shadow:0 2px 12px rgba(111,168,0,0.35);">
              ${num}
            </div>`
        } else {
          // Triángulo lima (SVG)
          pickupEl.innerHTML = `
            <div style="position:relative;width:36px;height:34px;display:flex;
              align-items:center;justify-content:center;">
              <svg width="36" height="34" viewBox="0 0 36 34" style="position:absolute;top:0;left:0;">
                <polygon points="18,2 1,33 35,33" fill="#FFFFFF"
                  stroke="#6FA800" stroke-width="2.5" stroke-linejoin="round"/>
              </svg>
              <span style="position:relative;z-index:1;font-family:Inter,sans-serif;
                font-weight:700;font-size:12px;color:#6FA800;margin-top:8px;">${num}</span>
            </div>`
        }

        const pickup = new Marker({ element: pickupEl, anchor: 'center' })
          .setLngLat([order.pickup.lng, order.pickup.lat])
          .addTo(map)
        markersRef.current.push(pickup)
      }

      // ── DROPOFF marker — óvalo naranja, siempre visible ──
      const dropoffEl = document.createElement('div')
      dropoffEl.style.cssText = 'cursor:pointer;'
      dropoffEl.innerHTML = `
        <div style="min-width:38px;height:26px;background:#C87000;
          border-radius:13px;border:2px solid #FFFFFF;
          display:flex;align-items:center;justify-content:center;
          padding:0 10px;
          font-family:Inter,sans-serif;font-weight:700;font-size:12px;color:#FFFFFF;
          box-shadow:0 2px 12px rgba(200,112,0,0.4);">
          ${num}
        </div>`

      const dropoff = new Marker({ element: dropoffEl, anchor: 'center' })
        .setLngLat([order.dropoff.lng, order.dropoff.lat])
        .addTo(map)
      markersRef.current.push(dropoff)
    })
  }, [activeOrders, ready])

  // ── Fit bounds to pickup/dropoff points ────────────────────
  // Opt-in static route preview (e.g. completed order detail),
  // where we want the whole A→B route framed instead of centering
  // on the driver's last known position.
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
      map.fitBounds(bounds, { padding: 64, duration: 600, maxZoom: 15 })
    }
  }, [activeOrders, ready, fitToRoute, showFullRoute])

  // ── Driver GPS marker ─────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    const el = document.createElement('div')
    el.style.cssText = 'width:32px;height:32px;position:relative;display:flex;align-items:center;justify-content:center;'
    el.innerHTML = `
      <div style="position:absolute;inset:0;background:#6FA800;border-radius:50%;opacity:0.3;animation:ping 2.5s cubic-bezier(0,0,0.2,1) infinite;"></div>
      <div style="position:absolute;inset:4px;background:#6FA800;border-radius:50%;opacity:0.2;"></div>
      <div style="position:relative;width:20px;height:20px;background:#6FA800;border-radius:50%;border:3px solid #FFFFFF;box-shadow:0 2px 8px rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;">
        <div style="width:5px;height:5px;background:#FFFFFF;border-radius:50%;"></div>
      </div>
    `

    const marker = new Marker({ element: el, anchor: 'center' })
      .setLngLat(getSavedPosition())
      .addTo(map)
    driverRef.current = marker

    const applyPosition = (pos: GeolocationPosition) => {
      const { longitude: lng, latitude: lat } = pos.coords
      const lngLat: [number, number] = [lng, lat]
      marker.setLngLat(lngLat)
      savePosition(lng, lat)
      if (followDriverRef.current && mapRef.current) {
        mapRef.current.easeTo({ center: lngLat, duration: 600, essential: true })
      }

      // Dynamic route slicing: recortar segmentos ya recorridos y anclar al vehículo
      const currentRoute = routeGeoJSONRef.current
      if (currentRoute?.coordinates && currentRoute.coordinates.length > 2 && mapRef.current) {
        const src = mapRef.current.getSource('route') as GeoJSONSource | undefined
        if (src) {
          const coords = currentRoute.coordinates
          let bestIdx = 0
          let minDist = Infinity
          for (let i = 0; i < coords.length; i++) {
            const d = (coords[i][0] - lng) ** 2 + (coords[i][1] - lat) ** 2
            if (d < minDist) {
              minDist = d
              bestIdx = i
            }
          }
          // Si está a menos de ~300m (0.003 deg) de algún punto de la ruta, recortamos los puntos anteriores
          if (minDist < 0.000009 && bestIdx > 0 && bestIdx < coords.length - 1) {
            const activeCoords: [number, number][] = [[lng, lat], ...coords.slice(bestIdx + 1)]
            src.setData({
              type: 'Feature',
              geometry: { type: 'LineString', coordinates: activeCoords },
              properties: {},
            })
          }
        }
      }
    }

    if (navigator.geolocation) {
      // Posición inicial inmediata — centra el mapa al instante
      navigator.geolocation.getCurrentPosition(applyPosition, () => {}, {
        enableHighAccuracy: true,
        timeout: 8000,
      })

      // Actualizaciones continuas mientras conduce
      watchRef.current = navigator.geolocation.watchPosition(
        applyPosition,
        () => {},
        { enableHighAccuracy: true, maximumAge: 3000 }
      )
    }

    return () => {
      marker.remove()
      if (watchRef.current !== null) navigator.geolocation.clearWatch(watchRef.current)
    }
  }, [ready])

  return (
    <div className={cn('relative overflow-hidden bg-[#dde3f0]', className)}>
      <div ref={wrapRef} className="w-full h-full" />

      {/* Error state */}
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
