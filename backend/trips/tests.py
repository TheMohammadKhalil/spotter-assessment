from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from rest_framework.test import APIClient

from trips.services.hos import DutyStatus, HOSScheduler, TimelineEvent
from trips.services.logs import build_daily_logs
from trips.services.planning import TripPlanner
from trips.services.routing import GeocodingError, Location, RouteInstruction, RouteLeg, RouteService


def leg(distance: float, duration_minutes: int, start_name: str = "Start", end_name: str = "End") -> RouteLeg:
    start = Location(start_name, 40.0, -90.0)
    end = Location(end_name, 41.0, -91.0)
    return RouteLeg(
        name=f"{start_name} to {end_name}",
        start=start,
        end=end,
        distance_miles=distance,
        duration_minutes=duration_minutes,
        geometry=[(start.lat, start.lng), (end.lat, end.lng)],
        instructions=[RouteInstruction(f"Drive from {start.name} to {end.name}.", distance, duration_minutes)],
    )


def schedule(
    first_leg: RouteLeg,
    second_leg: RouteLeg,
    current_cycle_used: float = 0,
    start: datetime | None = None,
    fuel_stop_duration_minutes: int = 30,
):
    scheduler = HOSScheduler(
        start or datetime(2026, 10, 2, 8, tzinfo=timezone.utc),
        current_cycle_used,
        fuel_stop_duration_minutes=fuel_stop_duration_minutes,
    )
    return scheduler.build(
        first_leg.start,
        first_leg.end,
        second_leg.end,
        [first_leg, second_leg],
    )


def timeline_event(
    event_id: str,
    status: DutyStatus,
    start: datetime,
    minutes: int,
    location_name: str,
    activity_type: str = "manual",
    start_location_name: str | None = None,
    end_location_name: str | None = None,
) -> TimelineEvent:
    location = Location(location_name, 40.0, -90.0)
    start_location = Location(start_location_name or location_name, 40.0, -90.0)
    end_location = Location(end_location_name or location_name, 40.0, -90.0)
    return TimelineEvent(
        id=event_id,
        status=status,
        activity_type=activity_type,
        start_time=start,
        end_time=start + timedelta(minutes=minutes),
        duration_minutes=minutes,
        location=location,
        start_location=start_location,
        end_location=end_location,
        distance_start_miles=0,
        distance_end_miles=0,
        description=f"{activity_type} at {location_name}",
        reason="test fixture",
    )


def graph_transition_count(log: dict) -> int:
    return sum(
        1
        for previous, current in zip(log["segments"], log["segments"][1:])
        if previous["status"] != current["status"]
    )


class HOSSchedulerTests(TestCase):
    def assert_hos_invariants(self, events, current_cycle_used=0):
        cycle_remaining = int(round((70 - current_cycle_used) * 60))
        drive_since_rest = 0
        drive_since_break = 0
        window_start = None

        for event in events:
            if event.status in {DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING} and window_start is None:
                window_start = event.start_time

            if event.status == DutyStatus.DRIVING:
                self.assertIsNotNone(window_start)
                self.assertLessEqual(event.end_time, window_start + timedelta(hours=14))
                drive_since_rest += event.duration_minutes
                drive_since_break += event.duration_minutes
                self.assertLessEqual(drive_since_rest, 11 * 60)
                self.assertLessEqual(drive_since_break, 8 * 60)

            if event.status in {DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING}:
                self.assertGreaterEqual(cycle_remaining, event.duration_minutes)
                cycle_remaining -= event.duration_minutes

            if event.activity_type == "restart":
                self.assertEqual(event.duration_minutes, 34 * 60)
                cycle_remaining = 70 * 60
                drive_since_rest = 0
                drive_since_break = 0
                window_start = None
            elif event.status in {DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH}:
                if event.duration_minutes >= 10 * 60:
                    drive_since_rest = 0
                    drive_since_break = 0
                    window_start = None
                elif event.duration_minutes >= 30:
                    drive_since_break = 0
            elif event.status == DutyStatus.ON_DUTY_NOT_DRIVING and event.duration_minutes >= 30:
                drive_since_break = 0

    def test_short_trip_under_eight_hours_needs_no_break_or_rest(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(300, 300, "Pickup", "Dropoff"))

        self.assert_hos_invariants(events)
        self.assertFalse(any(event.activity_type == "break" for event in events))
        self.assertFalse(any(event.activity_type == "rest" for event in events))

    def test_exactly_eight_hours_driving_does_not_force_break_without_more_driving(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(480, 480, "Pickup", "Dropoff"))

        self.assert_hos_invariants(events)
        self.assertFalse(any(event.activity_type == "break" for event in events))

    def test_more_than_eight_hours_driving_inserts_break_before_more_driving(self):
        events = schedule(leg(10, 10, "Current", "Pickup"), leg(700, 760, "Pickup", "Dropoff"))

        self.assert_hos_invariants(events)
        self.assertTrue(any(event.activity_type == "break" for event in events))

    def test_exactly_eleven_hours_driving_does_not_force_rest_without_more_driving(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(660, 660, "Pickup", "Dropoff"))

        self.assert_hos_invariants(events)
        self.assertFalse(any(event.activity_type == "rest" for event in events))

    def test_more_than_eleven_hours_driving_inserts_ten_hour_rest(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(720, 720, "Pickup", "Dropoff"))

        self.assert_hos_invariants(events)
        self.assertTrue(any(event.activity_type == "rest" and event.duration_minutes == 600 for event in events))

    def test_fourteen_hour_window_can_limit_before_eleven_driving_hours(self):
        events = schedule(
            leg(0, 1, "Current", "Pickup"),
            leg(2200, 660, "Pickup", "Dropoff"),
            fuel_stop_duration_minutes=90,
        )

        self.assert_hos_invariants(events)
        self.assertTrue(any("14-hour" in event.reason for event in events if event.activity_type == "rest"))

    def test_zero_cycle_used_does_not_insert_unneeded_restart(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(120, 120, "Pickup", "Dropoff"), 0)

        self.assert_hos_invariants(events, 0)
        self.assertFalse(any(event.activity_type == "restart" for event in events))

    def test_sixty_nine_cycle_hours_used_restarts_when_remaining_hour_is_consumed(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(120, 120, "Pickup", "Dropoff"), 69)

        self.assert_hos_invariants(events, 69)
        self.assertTrue(any(event.activity_type == "restart" for event in events))

    def test_seventy_cycle_hours_used_restarts_before_pickup(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(60, 60, "Pickup", "Dropoff"), 70)

        self.assertEqual(events[0].activity_type, "restart")
        self.assert_hos_invariants(events, 70)

    def test_trip_just_under_one_thousand_miles_does_not_fuel(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(999, 999, "Pickup", "Dropoff"))

        self.assert_hos_invariants(events)
        self.assertFalse(any(event.activity_type == "fuel" for event in events))

    def test_trip_just_over_one_thousand_miles_fuels_before_target(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(1001, 1001, "Pickup", "Dropoff"))
        fuel_events = [event for event in events if event.activity_type == "fuel"]

        self.assert_hos_invariants(events)
        self.assertTrue(fuel_events)
        self.assertLessEqual(fuel_events[0].distance_start_miles, 950)

    def test_route_over_two_thousand_miles_keeps_fuel_gaps_under_limit(self):
        events = schedule(leg(0, 1, "Current", "Pickup"), leg(2400, 2400, "Pickup", "Dropoff"))
        fuel_distances = [event.distance_start_miles for event in events if event.activity_type == "fuel"]
        final_distance = max(event.distance_end_miles for event in events)
        checkpoints = [0, *fuel_distances, final_distance]

        self.assert_hos_invariants(events)
        self.assertGreaterEqual(len(fuel_distances), 2)
        for previous, current in zip(checkpoints, checkpoints[1:]):
            self.assertLessEqual(current - previous, 1000)

    def test_current_and_pickup_can_be_identical(self):
        events = schedule(leg(0, 1, "Same Place", "Same Place"), leg(90, 90, "Same Place", "Dropoff"))

        self.assert_hos_invariants(events)
        self.assertEqual(events[0].activity_type, "pickup")

    def test_daily_logs_do_not_create_empty_day_when_trip_ends_at_midnight(self):
        events = schedule(
            leg(0, 1, "Current", "Pickup"),
            leg(0, 1, "Pickup", "Dropoff"),
            start=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
        )
        logs = build_daily_logs(events)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["date"], "2026-10-02")
        self.assertEqual(logs[0]["total_hours"], 24)

    def test_event_crossing_midnight_splits_logs_and_totals(self):
        events = schedule(
            leg(0, 1, "Current", "Pickup"),
            leg(0, 1, "Pickup", "Dropoff"),
            start=datetime(2026, 10, 2, 22, 30, tzinfo=timezone.utc),
        )
        logs = build_daily_logs(events)

        self.assertEqual([log["date"] for log in logs], ["2026-10-02", "2026-10-03"])
        self.assertTrue(all(log["total_hours"] == 24 for log in logs))
        self.assertTrue(all(set(log["totals"]) == {status.value for status in DutyStatus} for log in logs))


class DailyLogRemarksTests(TestCase):
    def test_every_status_change_produces_one_remark_from_graph_timeline(self):
        start = datetime(2026, 10, 2, tzinfo=timezone.utc)
        events = [
            timeline_event("evt-1", DutyStatus.OFF_DUTY, start, 60, "Boston"),
            timeline_event("evt-2", DutyStatus.DRIVING, start + timedelta(hours=1), 123, "En route to Boston", "drive", "Boston"),
            timeline_event("evt-3", DutyStatus.ON_DUTY_NOT_DRIVING, start + timedelta(hours=3, minutes=3), 30, "Boston", "fuel"),
            timeline_event("evt-4", DutyStatus.DRIVING, start + timedelta(hours=3, minutes=33), 89, "Boston", "drive", "Boston"),
            timeline_event("evt-5", DutyStatus.ON_DUTY_NOT_DRIVING, start + timedelta(hours=5, minutes=2), 58, "Boston", "dropoff"),
        ]

        log = build_daily_logs(events)[0]

        self.assertEqual(
            [(remark["time"], remark["status"]) for remark in log["remarks"]],
            [
                ("01:00", "Driving"),
                ("03:03", "On Duty (Not Driving)"),
                ("03:33", "Driving"),
                ("05:02", "On Duty (Not Driving)"),
                ("06:00", "Off Duty"),
            ],
        )
        self.assertEqual(graph_transition_count(log), len(log["remarks"]))
        self.assertIn("Fuel stop near Boston", log["remarks"][1]["note"])
        self.assertIn("Dropoff - Boston", log["remarks"][3]["note"])

    def test_adjacent_same_status_events_do_not_create_duplicate_remarks(self):
        start = datetime(2026, 10, 2, 1, tzinfo=timezone.utc)
        events = [
            timeline_event("evt-1", DutyStatus.DRIVING, start, 123, "En route", "drive", "Boston"),
            timeline_event("evt-2", DutyStatus.ON_DUTY_NOT_DRIVING, start + timedelta(minutes=123), 17, "Boston", "fuel"),
            timeline_event("evt-3", DutyStatus.ON_DUTY_NOT_DRIVING, start + timedelta(minutes=140), 13, "Boston", "inspection"),
            timeline_event("evt-4", DutyStatus.DRIVING, start + timedelta(minutes=153), 60, "En route", "drive", "Boston"),
        ]

        log = build_daily_logs(events)[0]

        self.assertEqual([remark["time"] for remark in log["remarks"]], ["01:00", "03:03", "03:33", "04:33"])
        self.assertNotIn("03:20", [remark["time"] for remark in log["remarks"]])
        self.assertEqual(graph_transition_count(log), len(log["remarks"]))

    def test_midnight_split_with_unchanged_status_does_not_create_false_remark(self):
        start = datetime(2026, 10, 2, 23, tzinfo=timezone.utc)
        events = [timeline_event("evt-1", DutyStatus.OFF_DUTY, start, 180, "Boston", "rest")]

        logs = build_daily_logs(events)

        self.assertEqual([log["date"] for log in logs], ["2026-10-02", "2026-10-03"])
        self.assertEqual(logs[1]["remarks"], [])
        self.assertEqual(graph_transition_count(logs[1]), 0)

    def test_transitions_into_all_duty_statuses_are_included(self):
        start = datetime(2026, 10, 2, tzinfo=timezone.utc)
        events = [
            timeline_event("evt-1", DutyStatus.OFF_DUTY, start, 60, "Boston"),
            timeline_event("evt-2", DutyStatus.DRIVING, start + timedelta(hours=1), 60, "En route", "drive", "Boston"),
            timeline_event("evt-3", DutyStatus.SLEEPER_BERTH, start + timedelta(hours=2), 60, "Boston", "sleeper"),
            timeline_event("evt-4", DutyStatus.ON_DUTY_NOT_DRIVING, start + timedelta(hours=3), 60, "Boston", "pickup"),
        ]

        log = build_daily_logs(events)[0]

        self.assertEqual(
            [remark["status"] for remark in log["remarks"]],
            ["Driving", "Sleeper Berth", "On Duty (Not Driving)", "Off Duty"],
        )
        self.assertEqual([remark["time"] for remark in log["remarks"]], ["01:00", "02:00", "03:00", "04:00"])
        self.assertEqual(graph_transition_count(log), len(log["remarks"]))

    def test_remarks_are_sorted_and_match_event_transition_timestamps(self):
        start = datetime(2026, 10, 2, tzinfo=timezone.utc)
        events = [
            timeline_event("evt-3", DutyStatus.ON_DUTY_NOT_DRIVING, start + timedelta(hours=2, minutes=17), 45, "Boston", "pickup"),
            timeline_event("evt-1", DutyStatus.OFF_DUTY, start, 60, "Boston"),
            timeline_event("evt-2", DutyStatus.DRIVING, start + timedelta(hours=1), 77, "En route", "drive", "Boston"),
        ]

        log = build_daily_logs(events)[0]

        self.assertEqual([remark["time"] for remark in log["remarks"]], ["01:00", "02:17", "03:02"])
        self.assertEqual([remark["time"] for remark in log["remarks"]], sorted(remark["time"] for remark in log["remarks"]))
        self.assertEqual(graph_transition_count(log), len(log["remarks"]))




class TripPlannerConsistencyTests(TestCase):
    def test_summary_daily_logs_and_timeline_use_same_calendar_span(self):
        service = Mock()
        current = Location("Current", 40, -90)
        pickup = Location("Pickup", 40, -90)
        dropoff = Location("Dropoff", 41, -91)
        service.geocode.side_effect = [current, pickup, dropoff]
        service.route.return_value = [
            leg(0, 1, "Current", "Pickup"),
            leg(720, 720, "Pickup", "Dropoff"),
        ]
        plan = TripPlanner(route_service=service).plan(
            {
                "current_location": "Current",
                "pickup_location": "Pickup",
                "dropoff_location": "Dropoff",
                "current_cycle_used_hours": 0,
                "start_time": datetime(2026, 10, 2, 8, tzinfo=timezone.utc),
            }
        )

        self.assertEqual(plan["summary"]["days"], len(plan["daily_logs"]))
        stop_ids = {stop["id"] for stop in plan["stops"]}
        timeline_ids = {event["id"] for event in plan["timeline"]}
        self.assertTrue(stop_ids.issubset(timeline_ids))


class RouteServiceFailureTests(TestCase):
    def test_geocode_timeout_uses_known_city_fallback(self):
        with patch("trips.services.routing.requests.get", side_effect=requests.Timeout):
            location = RouteService().geocode("Chicago, IL")

        self.assertEqual(location.name, "Chicago, IL")
        self.assertAlmostEqual(location.lat, 41.8781)

    def test_unresolved_location_raises_validation_error(self):
        with patch("trips.services.routing.requests.get", side_effect=requests.Timeout):
            with self.assertRaises(GeocodingError):
                RouteService().geocode("not chicago")

    def test_invalid_geocoder_json_falls_back_without_500(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("bad json")

        with patch("trips.services.routing.requests.get", return_value=response):
            location = RouteService().geocode("Dallas, TX")

        self.assertEqual(location.name, "Dallas, TX")


class TripPlanAPITests(TestCase):
    def test_api_rejects_invalid_cycle_hours(self):
        response = APIClient().post(
            "/api/trips/plan/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Atlanta, GA",
                "current_cycle_used_hours": 71,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
