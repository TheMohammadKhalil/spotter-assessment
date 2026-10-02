from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Iterable

import requests
from django.conf import settings


@dataclass(frozen=True)
class Location:
    name: str
    lat: float
    lng: float

    def to_dict(self) -> dict:
        return {"name": self.name, "lat": self.lat, "lng": self.lng}


@dataclass(frozen=True)
class RouteInstruction:
    text: str
    distance_miles: float
    duration_minutes: float

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "distance_miles": round(self.distance_miles, 1),
            "duration_minutes": round(self.duration_minutes, 1),
        }


@dataclass(frozen=True)
class RouteLeg:
    name: str
    start: Location
    end: Location
    distance_miles: float
    duration_minutes: float
    geometry: list[tuple[float, float]]
    instructions: list[RouteInstruction]


CITY_FALLBACKS: dict[str, tuple[float, float]] = {
    "atlanta": (33.7490, -84.3880),
    "austin": (30.2672, -97.7431),
    "baltimore": (39.2904, -76.6122),
    "boston": (42.3601, -71.0589),
    "charlotte": (35.2271, -80.8431),
    "chicago": (41.8781, -87.6298),
    "cincinnati": (39.1031, -84.5120),
    "cleveland": (41.4993, -81.6944),
    "columbus": (39.9612, -82.9988),
    "dallas": (32.7767, -96.7970),
    "denver": (39.7392, -104.9903),
    "detroit": (42.3314, -83.0458),
    "houston": (29.7604, -95.3698),
    "indianapolis": (39.7684, -86.1581),
    "jacksonville": (30.3322, -81.6557),
    "kansas city": (39.0997, -94.5786),
    "las vegas": (36.1716, -115.1391),
    "los angeles": (34.0522, -118.2437),
    "louisville": (38.2527, -85.7585),
    "memphis": (35.1495, -90.0490),
    "miami": (25.7617, -80.1918),
    "milwaukee": (43.0389, -87.9065),
    "minneapolis": (44.9778, -93.2650),
    "nashville": (36.1627, -86.7816),
    "new orleans": (29.9511, -90.0715),
    "new york": (40.7128, -74.0060),
    "oklahoma city": (35.4676, -97.5164),
    "orlando": (28.5383, -81.3792),
    "philadelphia": (39.9526, -75.1652),
    "phoenix": (33.4484, -112.0740),
    "pittsburgh": (40.4406, -79.9959),
    "portland": (45.5152, -122.6784),
    "raleigh": (35.7796, -78.6382),
    "richmond": (37.5407, -77.4360),
    "saint louis": (38.6270, -90.1994),
    "salt lake city": (40.7608, -111.8910),
    "san antonio": (29.4241, -98.4936),
    "san diego": (32.7157, -117.1611),
    "san francisco": (37.7749, -122.4194),
    "seattle": (47.6062, -122.3321),
    "tampa": (27.9506, -82.4572),
    "washington": (38.9072, -77.0369),
}


class GeocodingError(ValueError):
    pass


class RouteService:
    def geocode(self, query: str) -> Location:
        clean_query = query.strip()
        if not clean_query:
            raise GeocodingError("Location cannot be blank.")

        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": clean_query, "format": "json", "limit": 1, "countrycodes": "us"},
                headers={"User-Agent": settings.GEOCODER_USER_AGENT},
                timeout=settings.GEOCODER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            if data:
                item = data[0]
                return Location(
                    name=item.get("display_name", clean_query).split(",")[0],
                    lat=float(item["lat"]),
                    lng=float(item["lon"]),
                )
        except (requests.RequestException, KeyError, TypeError, ValueError):
            pass

        key = _fallback_key(clean_query)
        if key in CITY_FALLBACKS:
            lat, lng = CITY_FALLBACKS[key]
            return Location(name=clean_query, lat=lat, lng=lng)

        for city, coords in CITY_FALLBACKS.items():
            if key.startswith(f"{city} ") or city.startswith(f"{key} "):
                lat, lng = coords
                return Location(name=clean_query, lat=lat, lng=lng)

        raise GeocodingError(
            f"Could not geocode '{query}'. Try a city/state format such as 'Chicago, IL'."
        )

    def route(self, current: Location, pickup: Location, dropoff: Location, average_speed_mph: float) -> list[RouteLeg]:
        return [
            self._route_leg("Current location to pickup", current, pickup, average_speed_mph),
            self._route_leg("Pickup to dropoff", pickup, dropoff, average_speed_mph),
        ]

    def _route_leg(self, name: str, start: Location, end: Location, average_speed_mph: float) -> RouteLeg:
        try:
            url = (
                "https://router.project-osrm.org/route/v1/driving/"
                f"{start.lng},{start.lat};{end.lng},{end.lat}"
            )
            response = requests.get(
                url,
                params={"overview": "full", "geometries": "geojson", "steps": "true"},
                timeout=settings.ROUTER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            route = data["routes"][0]
            leg = route["legs"][0]
            geometry = [(lat, lng) for lng, lat in route["geometry"]["coordinates"]]
            instructions = [
                RouteInstruction(
                    text=_step_text(step),
                    distance_miles=step["distance"] / 1609.344,
                    duration_minutes=step["duration"] / 60,
                )
                for step in leg.get("steps", [])
                if step.get("distance", 0) > 0
            ]
            return RouteLeg(
                name=name,
                start=start,
                end=end,
                distance_miles=route["distance"] / 1609.344,
                duration_minutes=route["duration"] / 60,
                geometry=geometry or [(start.lat, start.lng), (end.lat, end.lng)],
                instructions=instructions[:24],
            )
        except (requests.RequestException, KeyError, IndexError, ValueError):
            distance = haversine_miles(start, end) * 1.18
            duration = (distance / average_speed_mph) * 60
            return RouteLeg(
                name=name,
                start=start,
                end=end,
                distance_miles=distance,
                duration_minutes=duration,
                geometry=_interpolate_line(start, end, points=18),
                instructions=[
                    RouteInstruction(
                        text=f"Drive from {start.name} to {end.name}.",
                        distance_miles=distance,
                        duration_minutes=duration,
                    )
                ],
            )


def haversine_miles(start: Location, end: Location) -> float:
    earth_radius_miles = 3958.7613
    lat1, lng1, lat2, lng2 = map(radians, [start.lat, start.lng, end.lat, end.lng])
    delta_lat = lat2 - lat1
    delta_lng = lng2 - lng1
    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_miles * c


def point_along_geometry(geometry: list[tuple[float, float]], fraction: float) -> tuple[float, float]:
    if not geometry:
        return (0.0, 0.0)
    if fraction <= 0:
        return geometry[0]
    if fraction >= 1:
        return geometry[-1]

    segment_lengths = [
        haversine_miles(
            Location("", geometry[index][0], geometry[index][1]),
            Location("", geometry[index + 1][0], geometry[index + 1][1]),
        )
        for index in range(len(geometry) - 1)
    ]
    total = sum(segment_lengths)
    if total <= 0:
        return geometry[-1]

    target = total * fraction
    travelled = 0.0
    for index, length in enumerate(segment_lengths):
        if travelled + length >= target:
            local_fraction = (target - travelled) / length if length else 0
            lat1, lng1 = geometry[index]
            lat2, lng2 = geometry[index + 1]
            return (
                lat1 + (lat2 - lat1) * local_fraction,
                lng1 + (lng2 - lng1) * local_fraction,
            )
        travelled += length
    return geometry[-1]


def flatten_geometry(legs: Iterable[RouteLeg]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for leg in legs:
        for point in leg.geometry:
            if not points or points[-1] != point:
                points.append(point)
    return points


def _fallback_key(query: str) -> str:
    city = query.lower().split(",")[0].strip()
    return " ".join(city.replace(".", "").split())


def _interpolate_line(start: Location, end: Location, points: int) -> list[tuple[float, float]]:
    return [
        (
            start.lat + (end.lat - start.lat) * index / (points - 1),
            start.lng + (end.lng - start.lng) * index / (points - 1),
        )
        for index in range(points)
    ]


def _step_text(step: dict) -> str:
    maneuver = step.get("maneuver", {})
    road = step.get("name") or "the route"
    kind = maneuver.get("type", "continue").replace("_", " ")
    modifier = maneuver.get("modifier")
    if modifier:
        return f"{kind.title()} {modifier} onto {road}."
    return f"{kind.title()} on {road}."

