import { useRef, useEffect, useState } from 'react'
import {
  Map as MLMap,
  Marker,
  AttributionControl,
  NavigationControl,
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
}

const MONTERREY: [number, number] = [-100.3161, 25.6866]

const PLATFORM_COLORS: Record<string, string> = {
  uber: '#FFFFFF',
  rappi: '#EF4444',
  didi: '#F97316',
}

const KEY = import.meta.env.VITE_MAPTILER_KEY

function buildStyle(): StyleSpecification {
  // Raster tiles — simpler and more reliable than fetching a style JSON
  const tiles = KEY
    ? [`https://api.maptiler.com/maps/dataviz-dark/{z}/{x}/{y}.png?key=${KEY}`]
    : [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
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
}: MockMapProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MLMap | null>(null)
  const markersRef = useRef<Marker[]>([])
  const driverRef = useRef<Marker | null>(null)
  const watchRef = useRef<number | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
          center: MONTERREY,
          zoom: 13,
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
            id: 'route-casing',
            type: 'line',
            source: 'route',
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': '#0B1215', 'line-width': 8, 'line-opacity': 0.6 },
          })
          map!.addLayer({
            id: 'route-line',
            type: 'line',
            source: 'route',
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': '#00C875', 'line-width': 4 },
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
    src.setData(
      routeGeoJSON
        ? { type: 'Feature', geometry: routeGeoJSON, properties: {} }
        : { type: 'FeatureCollection', features: [] }
    )
  }, [routeGeoJSON, ready])

  // ── Pickup + Dropoff markers ──────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []

    activeOrders.forEach((order, i) => {
      const platformColor = PLATFORM_COLORS[order.platform] ?? '#94A3B8'
      const num = String(i + 1)

      // ── Pickup marker (circle verde — "Recoger") ──
      const pickupEl = document.createElement('div')
      pickupEl.style.cssText = `
        width:32px;height:32px;background:#11191D;border:2.5px solid #00C875;
        border-radius:50%;display:flex;align-items:center;justify-content:center;
        font-family:Inter,sans-serif;font-weight:700;font-size:13px;color:${platformColor};
        box-shadow:0 2px 10px rgba(0,0,0,0.7);cursor:pointer;position:relative;
      `
      pickupEl.innerHTML = `
        <span>${num}</span>
        <div style="position:absolute;top:-6px;right:-6px;width:14px;height:14px;background:#00C875;
          border-radius:50%;border:1.5px solid #0B1215;display:flex;align-items:center;
          justify-content:center;font-size:8px;color:#0B1215;font-weight:900;line-height:1;">R</div>
      `
      const pickup = new Marker({ element: pickupEl, anchor: 'center' })
        .setLngLat([order.pickup.lng, order.pickup.lat])
        .addTo(map)
      markersRef.current.push(pickup)

      // ── Dropoff marker (teardrop naranja — "Entregar") ──
      const dropoffEl = document.createElement('div')
      dropoffEl.style.cssText = `
        width:28px;height:36px;display:flex;flex-direction:column;
        align-items:center;cursor:pointer;
      `
      dropoffEl.innerHTML = `
        <div style="width:28px;height:28px;background:#F5A524;border:2px solid #0B1215;
          border-radius:50% 50% 50% 0;transform:rotate(-45deg);
          box-shadow:0 2px 10px rgba(0,0,0,0.7);display:flex;align-items:center;
          justify-content:center;">
          <span style="transform:rotate(45deg);font-family:Inter,sans-serif;
            font-weight:900;font-size:11px;color:#0B1215;">${num}</span>
        </div>
        <div style="width:2px;height:8px;background:#F5A524;margin-top:0;"></div>
      `
      const dropoff = new Marker({ element: dropoffEl, anchor: 'bottom' })
        .setLngLat([order.dropoff.lng, order.dropoff.lat])
        .addTo(map)
      markersRef.current.push(dropoff)
    })
  }, [activeOrders, ready])

  // ── Driver GPS marker ─────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    const el = document.createElement('div')
    el.style.cssText = 'width:24px;height:24px;position:relative;'
    el.innerHTML = `
      <div style="position:absolute;inset:0;background:#00C875;border-radius:50%;opacity:0.3;animation:ping 2s cubic-bezier(0,0,0.2,1) infinite;"></div>
      <div style="position:absolute;inset:4px;background:#00C875;border-radius:50%;border:2.5px solid #0B1215;box-shadow:0 0 8px rgba(0,200,117,0.5);"></div>
    `

    const marker = new Marker({ element: el, anchor: 'center' })
      .setLngLat(MONTERREY)
      .addTo(map)
    driverRef.current = marker

    if (navigator.geolocation) {
      watchRef.current = navigator.geolocation.watchPosition(
        (pos) => marker.setLngLat([pos.coords.longitude, pos.coords.latitude]),
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
    <div className={cn('relative overflow-hidden bg-[#0B1215]', className)}>
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
          <div className="bg-black/70 backdrop-blur-sm text-vygo-secondary text-[10px] px-3 py-1.5 rounded-full border border-vygo-border">
            Agrega <code className="text-vygo-warning">VITE_MAPTILER_KEY</code> para mapa vectorial
          </div>
        </div>
      )}
    </div>
  )
}
