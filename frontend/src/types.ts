export type DutyStatus = 'OFF_DUTY' | 'SLEEPER_BERTH' | 'DRIVING' | 'ON_DUTY_NOT_DRIVING'

export type LocationPoint = {
  name: string
  lat: number
  lng: number
}

export type TimelineEvent = {
  id: string
  status: DutyStatus
  activity_type: string
  start_time: string
  end_time: string
  duration_minutes: number
  location: LocationPoint
  start_location: LocationPoint
  end_location: LocationPoint
  distance_start_miles: number
  distance_end_miles: number
  description: string
  reason: string
}

export type RouteInstruction = {
  leg: string
  text: string
  distance_miles: number
  duration_minutes: number
}

export type TripStop = {
  id: string
  type: string
  status: DutyStatus
  start_time: string
  end_time: string
  duration_minutes: number
  location: LocationPoint
  description: string
  reason: string
  distance_miles: number
}

export type DailyLogSegment = {
  status: DutyStatus
  start_time: string
  end_time: string
  start_minute: number
  end_minute: number
  duration_minutes: number
  description: string
  event_id?: string
  activity_type?: string
  location?: LocationPoint
}

export type DailyLog = {
  date: string
  origin: string
  destination: string
  segments: DailyLogSegment[]
  totals: Record<DutyStatus, number>
  total_hours: number
  driving_miles: number
  remarks: Array<{
    time: string
    status: string
    location: string
    note: string
  }>
}

export type TripPlan = {
  inputs: Record<string, string | number>
  route: {
    distance_miles: number
    duration_minutes: number
    geometry: Array<{ lat: number; lng: number }>
    legs: Array<{
      name: string
      start: LocationPoint
      end: LocationPoint
      distance_miles: number
      duration_minutes: number
    }>
    instructions: RouteInstruction[]
  }
  timeline: TimelineEvent[]
  stops: TripStop[]
  daily_logs: DailyLog[]
  summary: {
    total_distance_miles: number
    estimated_drive_hours: number
    total_elapsed_hours: number
    on_duty_hours: number
    off_duty_hours: number
    fuel_stops: number
    ten_hour_rests: number
    cycle_restarts: number
    initial_cycle_available_hours: number
    starts_at: string
    ends_at: string
    days: number
  }
  hos_explanations: Array<{ title: string; body: string }>
}

export type TripRequest = {
  current_location: string
  pickup_location: string
  dropoff_location: string
  current_cycle_used_hours: number
  start_time: string
  average_speed_mph: number
}

