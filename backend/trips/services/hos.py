from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import count
from typing import Iterable

from .routing import Location, RouteLeg, point_along_geometry


class DutyStatus(StrEnum):
    OFF_DUTY = "OFF_DUTY"
    SLEEPER_BERTH = "SLEEPER_BERTH"
    DRIVING = "DRIVING"
    ON_DUTY_NOT_DRIVING = "ON_DUTY_NOT_DRIVING"


@dataclass
class TimelineEvent:
    id: str
    status: DutyStatus
    activity_type: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    location: Location
    start_location: Location
    end_location: Location
    distance_start_miles: float
    distance_end_miles: float
    description: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "activity_type": self.activity_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.duration_minutes,
            "location": self.location.to_dict(),
            "start_location": self.start_location.to_dict(),
            "end_location": self.end_location.to_dict(),
            "distance_start_miles": round(self.distance_start_miles, 1),
            "distance_end_miles": round(self.distance_end_miles, 1),
            "description": self.description,
            "reason": self.reason,
        }


@dataclass
class DriveTask:
    leg: RouteLeg
    activity_type: str
    distance_start_miles: float
    distance_end_miles: float


class HOSScheduler:
    MAX_DRIVE_MINUTES = 11 * 60
    MAX_WINDOW_MINUTES = 14 * 60
    BREAK_TRIGGER_MINUTES = 8 * 60
    BREAK_DURATION_MINUTES = 30
    REST_DURATION_MINUTES = 10 * 60
    RESTART_DURATION_MINUTES = 34 * 60
    CYCLE_LIMIT_MINUTES = 70 * 60
    FUEL_TARGET_MILES = 950
    FUEL_HARD_LIMIT_MILES = 1000

    def __init__(
        self,
        start_time: datetime,
        current_cycle_used_hours: float,
        fuel_stop_duration_minutes: int = 30,
    ) -> None:
        self.now = start_time
        self.cycle_available_minutes = max(
            0, int(round((70 - current_cycle_used_hours) * 60))
        )
        self.fuel_stop_duration_minutes = fuel_stop_duration_minutes
        self.duty_window_start: datetime | None = None
        self.drive_since_rest_minutes = 0
        self.drive_since_break_minutes = 0
        self.miles_since_fuel = 0.0
        self.absolute_distance_miles = 0.0
        self.total_trip_distance_miles = 0.0
        self.current_location: Location | None = None
        self.events: list[TimelineEvent] = []
        self._ids = count(1)

    def build(self, current: Location, pickup: Location, dropoff: Location, legs: list[RouteLeg]) -> list[TimelineEvent]:
        self.current_location = current
        self.total_trip_distance_miles = sum(leg.distance_miles for leg in legs)
        first_leg, second_leg = legs

        self._drive_leg(
            DriveTask(
                leg=first_leg,
                activity_type="drive_to_pickup",
                distance_start_miles=0,
                distance_end_miles=first_leg.distance_miles,
            )
        )
        self._add_work_event(
            status=DutyStatus.ON_DUTY_NOT_DRIVING,
            activity_type="pickup",
            duration_minutes=60,
            location=pickup,
            description=f"Pickup freight at {pickup.name}.",
            reason="Assignment assumption: pickup consumes 1 hour on duty.",
        )
        self._drive_leg(
            DriveTask(
                leg=second_leg,
                activity_type="drive_to_dropoff",
                distance_start_miles=first_leg.distance_miles,
                distance_end_miles=first_leg.distance_miles + second_leg.distance_miles,
            )
        )
        self._add_work_event(
            status=DutyStatus.ON_DUTY_NOT_DRIVING,
            activity_type="dropoff",
            duration_minutes=60,
            location=dropoff,
            description=f"Drop off freight at {dropoff.name}.",
            reason="Assignment assumption: dropoff consumes 1 hour on duty.",
        )
        return self.events

    def _drive_leg(self, task: DriveTask) -> None:
        remaining_miles = task.leg.distance_miles
        remaining_minutes = max(1, int(round(task.leg.duration_minutes)))
        leg_elapsed_miles = 0.0

        while remaining_miles > 0.05 and remaining_minutes > 0:
            self._prepare_to_drive()

            speed_miles_per_minute = remaining_miles / remaining_minutes
            remaining_trip_miles = max(0.0, self.total_trip_distance_miles - self.absolute_distance_miles)
            if self.miles_since_fuel + remaining_trip_miles <= self.FUEL_HARD_LIMIT_MILES:
                minutes_until_fuel = remaining_minutes
            else:
                miles_until_fuel = self.FUEL_TARGET_MILES - self.miles_since_fuel
                minutes_until_fuel = int(max(0, miles_until_fuel / speed_miles_per_minute))

            if minutes_until_fuel <= 0:
                fraction = leg_elapsed_miles / task.leg.distance_miles if task.leg.distance_miles else 0
                self._insert_fuel_stop(task.leg, fraction)
                continue

            allowed_minutes = min(
                remaining_minutes,
                self.MAX_DRIVE_MINUTES - self.drive_since_rest_minutes,
                self._window_remaining_minutes(),
                self.BREAK_TRIGGER_MINUTES - self.drive_since_break_minutes,
                self.cycle_available_minutes,
                minutes_until_fuel,
            )

            if allowed_minutes <= 0:
                self._resolve_blocker()
                continue

            drive_minutes = max(1, int(allowed_minutes))
            miles = min(remaining_miles, speed_miles_per_minute * drive_minutes)
            fraction_start = leg_elapsed_miles / task.leg.distance_miles if task.leg.distance_miles else 0
            fraction_end = (leg_elapsed_miles + miles) / task.leg.distance_miles if task.leg.distance_miles else 1
            start_location = self._location_on_leg(task.leg, fraction_start)
            end_location = self._location_on_leg(task.leg, fraction_end)
            absolute_start = task.distance_start_miles + leg_elapsed_miles
            absolute_end = absolute_start + miles

            self._append_event(
                status=DutyStatus.DRIVING,
                activity_type=task.activity_type,
                duration_minutes=drive_minutes,
                location=end_location,
                start_location=start_location,
                end_location=end_location,
                distance_start_miles=absolute_start,
                distance_end_miles=absolute_end,
                description=f"Drive toward {task.leg.end.name}.",
                reason="Driving segment scheduled within 11-hour, 14-hour, break, fuel, and cycle limits.",
            )
            self.drive_since_rest_minutes += drive_minutes
            self.drive_since_break_minutes += drive_minutes
            self.cycle_available_minutes -= drive_minutes
            self.miles_since_fuel += miles
            self.absolute_distance_miles = absolute_end
            self.current_location = end_location
            remaining_miles -= miles
            remaining_minutes -= drive_minutes
            leg_elapsed_miles += miles

    def _prepare_to_drive(self) -> None:
        while True:
            if self.cycle_available_minutes <= 0:
                self._insert_restart()
                continue
            if self.drive_since_rest_minutes >= self.MAX_DRIVE_MINUTES:
                self._insert_rest("11-hour driving limit reached.")
                continue
            if self.duty_window_start is not None and self._window_remaining_minutes() <= 0:
                self._insert_rest("14-hour driving window expired.")
                continue
            if self.drive_since_break_minutes >= self.BREAK_TRIGGER_MINUTES:
                self._insert_break()
                continue
            if self.duty_window_start is None:
                self.duty_window_start = self.now
            return

    def _resolve_blocker(self) -> None:
        if self.cycle_available_minutes <= 0:
            self._insert_restart()
        elif self.drive_since_rest_minutes >= self.MAX_DRIVE_MINUTES:
            self._insert_rest("11-hour driving limit reached.")
        elif self.duty_window_start is not None and self._window_remaining_minutes() <= 0:
            self._insert_rest("14-hour driving window expired.")
        elif self.drive_since_break_minutes >= self.BREAK_TRIGGER_MINUTES:
            self._insert_break()
        else:
            self._insert_break()

    def _add_work_event(
        self,
        status: DutyStatus,
        activity_type: str,
        duration_minutes: int,
        location: Location,
        description: str,
        reason: str,
    ) -> None:
        if self.cycle_available_minutes < duration_minutes:
            self._insert_restart()
        if self.duty_window_start is None:
            self.duty_window_start = self.now

        self._append_event(
            status=status,
            activity_type=activity_type,
            duration_minutes=duration_minutes,
            location=location,
            start_location=location,
            end_location=location,
            distance_start_miles=self.absolute_distance_miles,
            distance_end_miles=self.absolute_distance_miles,
            description=description,
            reason=reason,
        )
        self.cycle_available_minutes -= duration_minutes
        self.current_location = location
        if duration_minutes >= self.BREAK_DURATION_MINUTES:
            self.drive_since_break_minutes = 0

    def _insert_break(self) -> None:
        location = self._current_location()
        self._append_event(
            status=DutyStatus.OFF_DUTY,
            activity_type="break",
            duration_minutes=self.BREAK_DURATION_MINUTES,
            location=location,
            start_location=location,
            end_location=location,
            distance_start_miles=self.absolute_distance_miles,
            distance_end_miles=self.absolute_distance_miles,
            description="Take a 30-minute non-driving break.",
            reason="Required after 8 cumulative hours of driving since the last qualifying break.",
        )
        self.drive_since_break_minutes = 0

    def _insert_rest(self, reason: str) -> None:
        location = self._current_location()
        self._append_event(
            status=DutyStatus.OFF_DUTY,
            activity_type="rest",
            duration_minutes=self.REST_DURATION_MINUTES,
            location=location,
            start_location=location,
            end_location=location,
            distance_start_miles=self.absolute_distance_miles,
            distance_end_miles=self.absolute_distance_miles,
            description="Take 10 consecutive hours off duty.",
            reason=reason,
        )
        self.duty_window_start = None
        self.drive_since_rest_minutes = 0
        self.drive_since_break_minutes = 0

    def _insert_restart(self) -> None:
        location = self._current_location()
        self._append_event(
            status=DutyStatus.OFF_DUTY,
            activity_type="restart",
            duration_minutes=self.RESTART_DURATION_MINUTES,
            location=location,
            start_location=location,
            end_location=location,
            distance_start_miles=self.absolute_distance_miles,
            distance_end_miles=self.absolute_distance_miles,
            description="Take a 34-hour restart.",
            reason="70-hour/8-day cycle availability is exhausted from the supplied current cycle usage.",
        )
        self.cycle_available_minutes = self.CYCLE_LIMIT_MINUTES
        self.duty_window_start = None
        self.drive_since_rest_minutes = 0
        self.drive_since_break_minutes = 0

    def _insert_fuel_stop(self, leg: RouteLeg, fraction: float) -> None:
        lat, lng = point_along_geometry(leg.geometry, fraction)
        location = Location(name=f"Fuel stop near {leg.end.name}", lat=lat, lng=lng)
        self._add_work_event(
            status=DutyStatus.ON_DUTY_NOT_DRIVING,
            activity_type="fuel",
            duration_minutes=self.fuel_stop_duration_minutes,
            location=location,
            description="Fuel vehicle.",
            reason="Fuel is scheduled before reaching 1,000 miles since the previous fuel event.",
        )
        self.miles_since_fuel = 0.0

    def _append_event(
        self,
        status: DutyStatus,
        activity_type: str,
        duration_minutes: int,
        location: Location,
        start_location: Location,
        end_location: Location,
        distance_start_miles: float,
        distance_end_miles: float,
        description: str,
        reason: str,
    ) -> None:
        start = self.now
        end = start + timedelta(minutes=duration_minutes)
        self.events.append(
            TimelineEvent(
                id=f"evt-{next(self._ids)}",
                status=status,
                activity_type=activity_type,
                start_time=start,
                end_time=end,
                duration_minutes=duration_minutes,
                location=location,
                start_location=start_location,
                end_location=end_location,
                distance_start_miles=distance_start_miles,
                distance_end_miles=distance_end_miles,
                description=description,
                reason=reason,
            )
        )
        self.now = end

    def _window_remaining_minutes(self) -> int:
        if self.duty_window_start is None:
            return self.MAX_WINDOW_MINUTES
        elapsed = int((self.now - self.duty_window_start).total_seconds() // 60)
        return self.MAX_WINDOW_MINUTES - elapsed

    def _current_location(self) -> Location:
        if self.current_location is None:
            raise RuntimeError("Scheduler current location is not initialized.")
        return self.current_location

    def _location_on_leg(self, leg: RouteLeg, fraction: float) -> Location:
        lat, lng = point_along_geometry(leg.geometry, fraction)
        if fraction <= 0:
            name = leg.start.name
        elif fraction >= 1:
            name = leg.end.name
        else:
            name = f"En route to {leg.end.name}"
        return Location(name=name, lat=lat, lng=lng)


def events_to_dict(events: Iterable[TimelineEvent]) -> list[dict]:
    return [event.to_dict() for event in events]
