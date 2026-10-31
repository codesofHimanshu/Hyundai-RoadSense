# Hyundai RoadSense — Starter MVP

A student prototype for sharing sensor-detected road-disturbance reports between simulated connected vehicles.

## Current milestone

This starter implements the backend API and SQLite storage. It does **not** yet read from an ESP32/MPU6050, prove that a report is a real pothole, or install on a Hyundai infotainment system.

## Requirements

- Python 3.10 or newer
- VS Code recommended

## Run on Windows PowerShell

Open PowerShell in this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

If PowerShell blocks activation, run this for the current terminal only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Open `http://127.0.0.1:8000/docs` for the interactive API.

## First demo

### 1. Report a simulated hazard

In `/docs`, expand `POST /api/hazards`, select **Try it out**, and use:

```json
{
  "event_type": "pothole",
  "latitude": 26.6337,
  "longitude": 92.8000,
  "confidence": 0.8,
  "source_vehicle": "vehicle-A"
}
```

Coordinates and confidence are illustrative test data, not a real detected pothole.

### 2. Ask for nearby hazards (simulated Vehicle B)

Use `GET /api/hazards/nearby` with:
- `latitude`: `26.6338`
- `longitude`: `92.8001`
- `radius_m`: `1000`
- `max_age_hours`: `24`

The response includes the report and approximate straight-line distance. This initial endpoint does **not** yet use road direction, route geometry, or map matching.

### API endpoints

- `GET /` — status
- `GET /health` — health check
- `POST /api/hazards` — submit a report with basic duplicate suppression
- `GET /api/hazards` — list reports
- `GET /api/hazards/nearby` — retrieve fresh reports within a radius
- `DELETE /api/hazards` — clear local prototype reports

## Roadmap

1. Run and test this API with simulated reports.
2. Add a React dashboard for the simulated approaching vehicle.
3. Add sensor data capture from ESP32 + MPU6050.
4. Build and evaluate a disturbance detector on labeled data.
5. Improve hazard relevance using vehicle direction/route information.
6. Test latency, false reports, stale reports, and duplicate suppression.

## Safety and claims

This is a research/ideathon prototype, not a production vehicle safety system. Reports may be incorrect. The UI should describe hazards as *reported* unless there is sufficient evidence to verify them. Warnings must remain advisory and must not control vehicle steering or braking.
