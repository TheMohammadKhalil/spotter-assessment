import type { TripPlan, TripRequest } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export async function planTrip(payload: TripRequest): Promise<TripPlan> {
  const response = await fetch(`${API_BASE_URL}/api/trips/plan/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(await formatApiError(response))
  }

  return response.json()
}

async function formatApiError(response: Response) {
  try {
    const error = await response.json()
    if (typeof error === 'string') return error
    if (error.detail) return String(error.detail)
    return Object.entries(error)
      .map(([field, value]) => `${humanize(field)}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
      .join(' | ')
  } catch {
    const text = await response.text()
    return text || 'Trip planning failed.'
  }
}

function humanize(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}
