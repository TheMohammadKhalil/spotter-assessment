from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .hos import DutyStatus, HOSScheduler, TimelineEvent, events_to_dict
from .logs import build_daily_logs
from .routing import GeocodingError, RouteLeg, RouteService, flatten_geometry


class TripPlanner:
    def __init__(self, route_service: RouteService | None = None) -> None:
        self.route_service = route_service or RouteService()

    def plan(self, data: dict) -> dict:
        start_time = data.get("start_time") or timezone.localtime(timezone.now()).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        if timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time, timezone.get_current_timezone())

        try:
            current = self.route_service.geocode(data["current_location"])
            pickup = self.route_service.geocode(data["pickup_location"])
            dropoff = self.route_service.geocode(data["dropoff_location"])
        except GeocodingError as exc:
            raise ValidationError({"location": str(exc)}) from exc

        average_speed_mph = data.get("average_speed_mph", 55)
        legs = self.route_service.route(current, pickup, dropoff, average_speed_mph)
        scheduler = HOSScheduler(
            start_time=start_time,
            current_cycle_used_hours=data["current_cycle_used_hours"],
            fuel_stop_duration_minutes=data.get("fuel_stop_duration_minutes", 30),
        )
        events = scheduler.build(current, pickup, dropoff, legs)
        daily_logs = build_daily_logs(events)

        return {
            "inputs": {
                "current_location": data["current_location"],
                "pickup_location": data["pickup_location"],
                "dropoff_location": data["dropoff_location"],
                "current_cycle_used_hours": data["current_cycle_used_hours"],
                "start_time": start_time.isoformat(),
            },
            "route": _build_route_payload(legs),
            "timeline": events_to_dict(events),
            "stops": _build_stops(events),
            "daily_logs": daily_logs,
            "summary": _build_summary(events, legs, data["current_cycle_used_hours"]),
            "hos_explanations": _build_explanations(),
        }


def _build_route_payload(legs: list[RouteLeg]) -> dict:
    instructions = []
    for leg in legs:
        instructions.extend(instruction.to_dict() | {"leg": leg.name} for instruction in leg.instructions)

    return {
        "distance_miles": round(sum(leg.distance_miles for leg in legs), 1),
        "duration_minutes": round(sum(leg.duration_minutes for leg in legs), 1),
        "geometry": [{"lat": lat, "lng": lng} for lat, lng in flatten_geometry(legs)],
        "legs": [
            {
                "name": leg.name,
                "start": leg.start.to_dict(),
                "end": leg.end.to_dict(),
                "distance_miles": round(leg.distance_miles, 1),
                "duration_minutes": round(leg.duration_minutes, 1),
            }
            for leg in legs
        ],
        "instructions": instructions,
    }


def _build_stops(events: list[TimelineEvent]) -> list[dict]:
    stop_types = {
        "pickup",
        "dropoff",
        "fuel",
        "break",
        "rest",
        "restart",
    }
    return [
        {
            "id": event.id,
            "type": event.activity_type,
            "status": event.status.value,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "duration_minutes": event.duration_minutes,
            "location": event.location.to_dict(),
            "description": event.description,
            "reason": event.reason,
            "distance_miles": round(event.distance_start_miles, 1),
        }
        for event in events
        if event.activity_type in stop_types
    ]


def _build_summary(events: list[TimelineEvent], legs: list[RouteLeg], current_cycle_used: float) -> dict:
    driving_minutes = sum(
        event.duration_minutes for event in events if event.status == DutyStatus.DRIVING
    )
    on_duty_minutes = sum(
        event.duration_minutes
        for event in events
        if event.status in {DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING}
    )
    off_duty_minutes = sum(
        event.duration_minutes
        for event in events
        if event.status in {DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH}
    )
    total_distance = sum(leg.distance_miles for leg in legs)
    cycle_restarts = sum(1 for event in events if event.activity_type == "restart")
    fuel_stops = sum(1 for event in events if event.activity_type == "fuel")
    trip_start = events[0].start_time if events else None
    trip_end = events[-1].end_time if events else None

    return {
        "total_distance_miles": round(total_distance, 1),
        "estimated_drive_hours": round(driving_minutes / 60, 2),
        "total_elapsed_hours": round((trip_end - trip_start).total_seconds() / 3600, 2) if trip_start and trip_end else 0,
        "on_duty_hours": round(on_duty_minutes / 60, 2),
        "off_duty_hours": round(off_duty_minutes / 60, 2),
        "fuel_stops": fuel_stops,
        "ten_hour_rests": sum(1 for event in events if event.activity_type == "rest"),
        "cycle_restarts": cycle_restarts,
        "current_cycle_used_hours": current_cycle_used,
        "initial_cycle_available_hours": round(70 - current_cycle_used, 2),
        "starts_at": trip_start.isoformat() if trip_start else None,
        "ends_at": trip_end.isoformat() if trip_end else None,
        "days": _calendar_days_spanned(events),
    }


def _calendar_days_spanned(events: list[TimelineEvent]) -> int:
    if not events:
        return 0
    last_activity = events[-1].end_time - timedelta(microseconds=1)
    if last_activity < events[0].start_time:
        last_activity = events[0].start_time
    return (last_activity.date() - events[0].start_time.date()).days + 1


def _build_explanations() -> list[dict]:
    return [
        {
            "title": "Canonical timeline",
            "body": "Map markers, route stops, duty totals, and daily log sheets are all derived from the same scheduled event list.",
        },
        {
            "title": "70-hour / 8-day cycle",
            "body": "Because only aggregate current cycle usage is supplied, the planner uses 70 minus current cycle hours as available time and inserts a 34-hour restart if that availability is exhausted.",
        },
        {
            "title": "30-minute break",
            "body": "The scheduler inserts a non-driving break before driving would exceed 8 cumulative hours since the last qualifying non-driving period.",
        },
        {
            "title": "Fuel planning",
            "body": "Fuel is targeted near 950 miles only when the remaining trip would otherwise exceed 1,000 miles since the prior fuel event.",
        },
        {
            "title": "14-hour window",
            "body": "Pickup, dropoff, fueling, and driving start or consume the 14-hour driving window. Ordinary 30-minute breaks do not pause that clock.",
        },
    ]
