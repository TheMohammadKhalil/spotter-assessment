import { useEffect, useRef } from 'react'
import L from 'leaflet'
import type { TripPlan } from '../types'

type Props = {
  plan: TripPlan
}

const markerColors: Record<string, string> = {
  pickup: '#2563eb',
  dropoff: '#16a34a',
  fuel: '#ca8a04',
  break: '#0891b2',
  rest: '#7c3aed',
  restart: '#dc2626',
}

export function MapView({ plan }: Props) {
  const mapRef = useRef<HTMLDivElement | null>(null)
  const instanceRef = useRef<L.Map | null>(null)

  useEffect(() => {
    if (!mapRef.current) return

    if (!instanceRef.current) {
      instanceRef.current = L.map(mapRef.current, {
        zoomControl: true,
        scrollWheelZoom: false,
      })

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(instanceRef.current)
    }

    const map = instanceRef.current
    map.eachLayer((layer) => {
      if (!(layer instanceof L.TileLayer)) {
        map.removeLayer(layer)
      }
    })

    const routePoints = plan.route.geometry.map((point) => [point.lat, point.lng] as L.LatLngTuple)
    if (routePoints.length >= 2) {
      const polyline = L.polyline(routePoints, {
        color: '#1d4ed8',
        weight: 5,
        opacity: 0.82,
      }).addTo(map)
      const bounds = polyline.getBounds()
      if (bounds.isValid()) {
        map.fitBounds(bounds.pad(0.18))
      }
    } else if (routePoints.length === 1) {
      map.setView(routePoints[0], 10)
    }

    const origin = plan.route.legs[0]?.start
    if (origin) {
      addMarker(map, origin, 'Current', '#111827')
    }

    plan.stops.forEach((stop) => {
      addMarker(map, stop.location, stop.type, markerColors[stop.type] ?? '#475569', stop.description)
    })

    return () => undefined
  }, [plan])

  return (
    <div className="map-shell">
      <div className="map-canvas" ref={mapRef} role="application" aria-label="Interactive route map with scheduled HOS stops" />
    </div>
  )
}


function addMarker(
  map: L.Map,
  point: { name: string; lat: number; lng: number },
  label: string,
  color: string,
  description?: string,
) {
  const icon = L.divIcon({
    className: 'custom-marker',
    html: `<span style="background:${escapeHtml(color)}">${escapeHtml(label.slice(0, 1).toUpperCase())}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })

  L.marker([point.lat, point.lng], { icon })
    .addTo(map)
    .bindPopup(
      `<strong>${escapeHtml(label)}</strong><br />${escapeHtml(point.name)}${
        description ? `<br />${escapeHtml(description)}` : ''
      }`,
    )
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}
