import { useRef, useEffect, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { cn } from '@/lib/utils'
import type { Order } from '@/types/order'

// Shape the routing algorithm should return
export interface RouteGeoJSON {
  type: 'LineString'
  coordinates: [number, number][] // [lng, lat][]
}

interface MockMapProps {
  activeOrders?: Order[]
  routeGeoJSON?: RouteGeoJSON | null   // pass this from your routing algorithm
  className?: string
  showFullRoute?: boolean
}

const MONTERREY: [number, number] = [-100.3161, 25.6866]

const PLATFORM_COLORS: Record<string, string> = {
  uber: '#FFFFFF',
  rappi: '#EF4444',
  didi: '#F97316',
}

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY

// Returns a dark map style.
// With VITE_MAPTILER_KEY → full vector dark (best quality).
// Without key → Esri World Dark Gray Canvas (free, no key, dark ✓).
function buildStyle(): maplibregl.StyleSpecification | string {
  if (MAPTILER_KEY) {
    return `https://api.maptiler.com/maps/dataviz-dark/style.json?key=${MAPTILER_KEY}`
  }
  // Esri World Dark Gray — no API key required
  // Note: Esri tile path format is {z}/{y}/{x} (y before x)
  return {
    version: 8,
    sources: {
      'esri-base': {
        type: 'raster',
        tiles: [
          'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        ],
        tileSize: 256,
        attribution: '© Esri, HERE, Garmin, © OpenStreetMap contributors',
        maxzoom: 16,
      },
      'esri-ref': {
        type: 'raster',
        tiles: [
          'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
        ],
        tileSize: 256,
        maxzoom: 16,
      },
    },
    layers: [
      { id: 'esri-base-layer', type: 'raster', source: 'esri-base' },
      { id: 'esri-ref-layer',  type: 'raster', source: 'esri-ref'  },
    ],
  } satisfies maplibregl.StyleSpecification
}

export function MockMap({ activeOrders = [], routeGeoJSON, className, showFullRoute = false }: MockMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])
  const driverMarkerRef = useRef<maplibregl.Marker | null>(null)
  const watchIdRef = useRef<number | null>(null)
  const [ready, setReady] = useState(false)

  // ── Init map ──────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: buildStyle(),
      center: MONTERREY,
      zoom: 13,
      attributionControl: false,
    })

    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left')
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')

    map.on('load', () => {
      // Route line source (updated externally via routeGeoJSON prop)
      map.addSource('route', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({
        id: 'route-casing',
        type: 'line',
        source: 'route',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#0B1215', 'line-width': 8, 'line-opacity': 0.6 },
      })
      map.addLayer({
        id: 'route-line',
        type: 'line',
        source: 'route',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#00C875', 'line-width': 4, 'line-opacity': 1 },
      })

      setReady(true)
    })

    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  // ── Update route GeoJSON ──────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const src = map.getSource('route') as maplibregl.GeoJSONSource | undefined
    if (!src) return

    src.setData(
      routeGeoJSON
        ? { type: 'Feature', geometry: routeGeoJSON, properties: {} }
        : { type: 'FeatureCollection', features: [] }
    )
  }, [routeGeoJSON, ready])

  // ── Update delivery markers ───────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []

    const bounds = new maplibregl.LngLatBounds()
    let hasBounds = false

    activeOrders.forEach((order, i) => {
      const color = PLATFORM_COLORS[order.platform] ?? '#94A3B8'
      const el = document.createElement('div')
      el.style.cssText = `
        width:32px;height:32px;
        background:#11191D;
        border:2px solid #00C875;
        border-radius:50%;
        display:flex;align-items:center;justify-content:center;
        font-family:Inter,sans-serif;font-weight:700;font-size:13px;
        color:${color};
        box-shadow:0 2px 10px rgba(0,0,0,0.6);
        cursor:pointer;
      `
      el.textContent = String(i + 1)

      const lngLat: [number, number] = [order.pickup.lng, order.pickup.lat]
      new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat(lngLat)
        .addTo(map)

      bounds.extend(lngLat)
      bounds.extend([order.dropoff.lng, order.dropoff.lat])
      hasBounds = true
    })

    if (hasBounds && activeOrders.length > 0) {
      map.fitBounds(bounds, { padding: 80, maxZoom: 15, duration: 800 })
    }
  }, [activeOrders, ready])

  // ── Driver position (real GPS) ────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    // Driver marker
    const el = document.createElement('div')
    el.style.cssText = 'width:24px;height:24px;position:relative;'
    el.innerHTML = `
      <div style="position:absolute;inset:0;background:#00C875;border-radius:50%;opacity:0.3;animation:ping 2s cubic-bezier(0,0,0.2,1) infinite;"></div>
      <div style="position:absolute;inset:4px;background:#00C875;border-radius:50%;border:2.5px solid #0B1215;box-shadow:0 0 8px rgba(0,200,117,0.5);"></div>
    `

    const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
      .setLngLat(MONTERREY)
      .addTo(map)
    driverMarkerRef.current = marker

    if (navigator.geolocation) {
      watchIdRef.current = navigator.geolocation.watchPosition(
        (pos) => {
          const coords: [number, number] = [pos.coords.longitude, pos.coords.latitude]
          marker.setLngLat(coords)
        },
        () => {}, // fallback to MONTERREY silently
        { enableHighAccuracy: true, maximumAge: 3000 }
      )
    }

    return () => {
      marker.remove()
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current)
      }
    }
  }, [ready])

  return (
    <div className={cn('relative overflow-hidden', className)}>
      <div ref={containerRef} className="w-full h-full" />

      {/* Tip para activar vector tiles — solo cuando no hay key */}
      {!MAPTILER_KEY && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-10 pointer-events-none whitespace-nowrap">
          <div className="bg-black/70 backdrop-blur-sm text-vygo-secondary text-[10px] px-3 py-1.5 rounded-full border border-vygo-border">
            Agrega <code className="text-vygo-warning">VITE_MAPTILER_KEY</code> en .env.local para vector tiles
          </div>
        </div>
      )}

      {showFullRoute && (
        <div className="absolute top-3 right-3 pointer-events-none z-10 bg-black/60 backdrop-blur-sm rounded-xl px-2.5 py-1.5 border border-vygo-border flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-vygo-green animate-pulse" />
          <span className="text-xs text-vygo-green font-medium">En vivo</span>
        </div>
      )}
    </div>
  )
}
