from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .hos import DutyStatus, TimelineEvent
from .routing import Location


STATUS_LABELS = {
    DutyStatus.OFF_DUTY: "Off Duty",
    DutyStatus.SLEEPER_BERTH: "Sleeper Berth",
    DutyStatus.DRIVING: "Driving",
    DutyStatus.ON_DUTY_NOT_DRIVING: "On Duty (Not Driving)",
}


@dataclass(frozen=True)
class LogEntry:
    status: DutyStatus
    activity_type: str
    start_time: datetime
    end_time: datetime
    location: Location
    description: str


def build_daily_logs(events: list[TimelineEvent]) -> list[dict]:
    if not events:
        return []

    ordered_events = sorted(events, key=lambda event: event.start_time)
    first_day = datetime.combine(ordered_events[0].start_time.date(), time.min, tzinfo=ordered_events[0].start_time.tzinfo)
    last_activity = ordered_events[-1].end_time - timedelta(microseconds=1)
    if last_activity < ordered_events[0].start_time:
        last_activity = ordered_events[0].start_time
    last_day = datetime.combine(last_activity.date(), time.min, tzinfo=ordered_events[-1].end_time.tzinfo)
    logs = []
    day = first_day

    while day <= last_day:
        logs.append(_build_day_log(day, ordered_events))
        day += timedelta(days=1)

    return logs


def _build_day_log(day_start: datetime, events: list[TimelineEvent]) -> dict:
    day_end = day_start + timedelta(days=1)
    entries: list[LogEntry] = []
    segments = []
    totals = defaultdict(float)
    driving_miles = 0.0

    clipped = []
    for event in events:
        start = max(event.start_time, day_start)
        end = min(event.end_time, day_end)
        if start >= end:
            continue
        clipped.append((event, start, end))

    cursor = day_start
    last_location: Location | None = None
    for event, start, end in clipped:
        if cursor < start:
            gap_location = last_location or event.start_location
            _append_log_entry(
                entries,
                segments,
                totals,
                DutyStatus.OFF_DUTY,
                "off_duty",
                cursor,
                start,
                day_start,
                gap_location,
                "Off duty",
            )

        segment = _append_log_entry(
            entries,
            segments,
            totals,
            event.status,
            event.activity_type,
            start,
            end,
            day_start,
            _remark_location(event),
            event.description,
        )
        segment["event_id"] = event.id
        segment["activity_type"] = event.activity_type
        segment["location"] = event.location.to_dict()

        fraction = (end - start).total_seconds() / max(1, (event.end_time - event.start_time).total_seconds())
        if event.status == DutyStatus.DRIVING:
            driving_miles += (event.distance_end_miles - event.distance_start_miles) * fraction
        last_location = event.end_location
        cursor = end

    if cursor < day_end:
        gap_location = last_location or (clipped[-1][0].end_location if clipped else Location("Off duty", 0, 0))
        _append_log_entry(
            entries,
            segments,
            totals,
            DutyStatus.OFF_DUTY,
            "off_duty",
            cursor,
            day_end,
            day_start,
            gap_location,
            "Off duty",
        )

    remarks = _build_remarks(entries, _status_before_day_start(events, day_start))
    totals_hours = {
        status.value: round(totals[status] / 60, 2)
        for status in DutyStatus
    }
    total_all = round(sum(totals.values()) / 60, 2)
    origin = clipped[0][0].start_location.name if clipped else "Off duty"
    destination = clipped[-1][0].end_location.name if clipped else "Off duty"

    return {
        "date": day_start.date().isoformat(),
        "origin": origin,
        "destination": destination,
        "segments": segments,
        "totals": totals_hours,
        "total_hours": total_all,
        "driving_miles": round(driving_miles, 1),
        "remarks": remarks,
    }


def _append_log_entry(
    entries: list[LogEntry],
    segments: list[dict],
    totals: defaultdict[DutyStatus, float],
    status: DutyStatus,
    activity_type: str,
    start: datetime,
    end: datetime,
    day_start: datetime,
    location: Location,
    description: str,
) -> dict:
    entries.append(LogEntry(status, activity_type, start, end, location, description))
    return _append_segment(segments, totals, status, start, end, day_start, description)


def _build_remarks(entries: list[LogEntry], previous_status: DutyStatus) -> list[dict]:
    remarks = []
    current_status = previous_status

    for entry in entries:
        if entry.status == current_status:
            continue
        remarks.append(
            {
                "time": entry.start_time.strftime("%H:%M"),
                "status": STATUS_LABELS[entry.status],
                "location": entry.location.name,
                "note": _remark_note(entry),
            }
        )
        current_status = entry.status

    return remarks


def _status_before_day_start(events: list[TimelineEvent], day_start: datetime) -> DutyStatus:
    previous_event_ending_at_midnight: TimelineEvent | None = None

    for event in events:
        if event.start_time < day_start < event.end_time:
            return event.status
        if event.end_time == day_start:
            previous_event_ending_at_midnight = event
        if event.start_time >= day_start:
            break

    if previous_event_ending_at_midnight is not None:
        return previous_event_ending_at_midnight.status
    return DutyStatus.OFF_DUTY


def _remark_location(event: TimelineEvent) -> Location:
    return event.start_location


def _remark_note(entry: LogEntry) -> str:
    location = entry.location.name.strip()
    activity_type = entry.activity_type

    if activity_type == "fuel":
        if location.lower().startswith("fuel stop"):
            return location
        return _join_note("Fuel stop near", location)
    if activity_type == "pickup":
        return _join_note("Pickup -", location)
    if activity_type == "dropoff":
        return _join_note("Dropoff -", location)
    if activity_type == "break":
        return _join_note("Required 30-minute break -", location)
    if activity_type == "rest":
        return _join_note("10-hour rest -", location)
    if activity_type == "restart":
        return _join_note("34-hour cycle restart -", location)
    if location:
        return location
    return entry.description


def _join_note(prefix: str, location: str) -> str:
    if not location:
        return prefix.rstrip(" -")
    return f"{prefix} {location}"


def _append_segment(
    segments: list[dict],
    totals: defaultdict[DutyStatus, float],
    status: DutyStatus,
    start: datetime,
    end: datetime,
    day_start: datetime,
    description: str,
) -> dict:
    duration_minutes = (end - start).total_seconds() / 60
    totals[status] += duration_minutes
    segment = {
        "status": status.value,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "start_minute": round((start - day_start).total_seconds() / 60, 2),
        "end_minute": round((end - day_start).total_seconds() / 60, 2),
        "duration_minutes": round(duration_minutes, 2),
        "description": description,
    }
    segments.append(segment)
    return segment
