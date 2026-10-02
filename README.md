# Spotter HOS Trip Planner

A full-stack Django + React assessment project for planning property-carrier trips under FMCSA-style Hours of Service rules.

The app accepts current, pickup, and dropoff locations plus current 70-hour/8-day cycle usage. It returns one canonical trip timeline that drives the route map, stop schedule, HOS explanations, trip summary, and ELD-style daily log sheets.

## Stack

- Backend: Python, Django, Django REST Framework
- Frontend: React, TypeScript, Vite, Material UI
- Maps: OpenStreetMap tiles with Leaflet
- Routing/geocoding: public OSRM and Nominatim APIs with deterministic fallbacks for common US cities

## Implemented HOS Assumptions

- Property-carrying CMV driver
- 70-hour / 8-day cycle
- No adverse driving conditions
- Fueling required before exceeding 1,000 miles since the last fuel event; fuel stops are targeted near 950 miles only when the remaining trip would otherwise exceed 1,000 miles
- 1 hour pickup and 1 hour dropoff
- 11-hour driving limit
- 14-hour driving window
- 30-minute break before driving beyond 8 cumulative driving hours
- 10-hour off-duty rest resets the 11-hour driving allowance and 14-hour window
- 34-hour restart resets cycle availability

The assessment gives only aggregate current cycle usage, not the prior 7 days of duty records. This app does not fabricate rolling historical duty logs. It uses `70 - current_cycle_used_hours` as available cycle time and schedules a 34-hour restart when that deterministic availability is exhausted.

## Local Setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver 8000
```

### Frontend

```bash
cd frontend
npm install
npm run lint
npm run build
npm run dev
```

Open `http://localhost:5173`.

If the backend is not running on `http://localhost:8000`, set:

```bash
VITE_API_BASE_URL=http://your-backend-host
```

## API

`POST /api/trips/plan/`

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Atlanta, GA",
  "current_cycle_used_hours": 12,
  "start_time": "2026-10-02T08:00:00",
  "average_speed_mph": 55
}
```

The response includes `route`, `timeline`, `stops`, `daily_logs`, `summary`, and `hos_explanations`. All views are derived from the same timeline.

## Environment Variables

Copy `.env.example` and configure as needed. Important variables:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CORS_ALLOW_ALL_ORIGINS`
- `GEOCODER_USER_AGENT`
- `GEOCODER_TIMEOUT_SECONDS`
- `ROUTER_TIMEOUT_SECONDS`
- `VITE_API_BASE_URL`

## Deployment Notes

- Backend can be deployed to Render, Railway, Fly.io, or any WSGI-compatible host.
- Frontend can be deployed to Vercel or Netlify.
- Set `VITE_API_BASE_URL` to the deployed backend URL.
- Configure backend `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` for the deployed frontend/backend domains.
- Keep `DJANGO_DEBUG=false` in production.

## Verification

```bash
cd backend
python manage.py test

cd ../frontend
npm run lint
npm run build
```

The backend tests include adversarial HOS scenarios for cycle exhaustion, 8/11/14-hour limits, fuel thresholds, midnight splitting, routing/geocoding failures, and API validation.

## Walkthrough Script

1. Show the input form and explain the four required assignment inputs.
2. Submit a sample trip and call out the map markers, stops, and route instructions.
3. Open the event timeline and explain that it is the canonical source for every downstream view.
4. Show the daily logs and totals, especially a multi-day trip.
5. In code, highlight `backend/trips/services/hos.py`, `planning.py`, and the React log/map components.
