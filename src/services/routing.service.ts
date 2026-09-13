type Coord = [number, number] // [lng, lat]
type LineString = { type: 'LineString'; coordinates: Coord[] }

const OSRM = 'https://router.project-osrm.org/route/v1/driving'

export async function fetchStreetRoute(waypoints: Coord[]): Promise<LineString | null> {
  if (waypoints.length < 2) return null
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 8000)
  try {
    const coords = waypoints.map(([lng, lat]) => `${lng},${lat}`).join(';')
    const res = await fetch(
      `${OSRM}/${coords}?geometries=geojson&overview=full`,
      { signal: controller.signal }
    )
    if (!res.ok) return null
    const data = await res.json()
    const geometry = data?.routes?.[0]?.geometry
    if (geometry?.type === 'LineString' && geometry.coordinates?.length > 1) {
      return geometry as LineString
    }
    return null
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}
