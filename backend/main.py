from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt
import os
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import pandas as pd
from ml.predict import RoadSensePredictor


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(
    os.getenv("ROADSENSE_DB", str(BASE_DIR / "data" / "roadsense.db"))
)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Synthetic coordinates used for the Vehicle B demonstration.
DEMO_LATITUDE = 26.6337
DEMO_LONGITUDE = 92.8000

DEMO_START_DISTANCE_M = 500.0
DEMO_SPEED_MPS = 10.0
AI_CONFIDENCE_THRESHOLD = 0.65
MODEL_PATH = BASE_DIR / "ml" / "models" / "roadsense_model.joblib"
DATASET_PATH = BASE_DIR / "simulation" / "data" / "roadsense_sensor_dataset.csv"


# ============================================================
# DATABASE
# ============================================================

def connect_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hazards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                confidence REAL NOT NULL,
                source_vehicle TEXT NOT NULL,
                reported_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
        """)
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_db()
    yield


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Hyundai RoadSense API",
    description=(
        "Prototype API for reporting and retrieving road-disturbance "
        "alerts, including a simulated Vehicle B warning system."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# VEHICLE B SIMULATION STATE
# ============================================================

vehicle_b_lock = Lock()

vehicle_b_state = {
    "running": False,
    "distance_from_hazard_m": DEMO_START_DISTANCE_M,
    "speed_mps": DEMO_SPEED_MPS,
    "last_updated": None,
}


# ============================================================
# REQUEST MODEL
# ============================================================

class AIPredictionRequest(BaseModel):
    """Named sensor features produced by the simulated Vehicle A."""

    features: dict[str, float]
    latitude: float = Field(default=DEMO_LATITUDE, ge=-90, le=90)
    longitude: float = Field(default=DEMO_LONGITUDE, ge=-180, le=180)
    source_vehicle: str = Field(default="vehicle-A", min_length=1, max_length=50)
    report_hazard: bool = True
    confidence_threshold: float = Field(
        default=AI_CONFIDENCE_THRESHOLD, ge=0, le=1
    )


class DemoPredictionRequest(BaseModel):
    """Run the model on one generated dataset sample for an easy demo."""

    sample_label: Literal["pothole", "bump", "normal", "uneven_road"] = "pothole"
    latitude: float = Field(default=DEMO_LATITUDE, ge=-90, le=90)
    longitude: float = Field(default=DEMO_LONGITUDE, ge=-180, le=180)
    source_vehicle: str = Field(default="vehicle-A", min_length=1, max_length=50)
    report_hazard: bool = True
    confidence_threshold: float = Field(
        default=AI_CONFIDENCE_THRESHOLD, ge=0, le=1
    )


class HazardReport(BaseModel):
    event_type: Literal[
        "pothole",
        "bump",
        "uneven_surface",
        "dip",
    ] = "uneven_surface"

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    confidence: float = Field(default=0.7, ge=0, le=1)

    source_vehicle: str = Field(
        default="vehicle-A",
        min_length=1,
        max_length=50,
    )


# ============================================================
# DISTANCE CALCULATION
# ============================================================

def haversine_m(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance between two GPS coordinates."""

    earth_radius_m = 6_371_000

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    a = min(1.0, max(0.0, a))

    return 2 * earth_radius_m * asin(sqrt(a))


# ============================================================
# BASIC ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "project": "Hyundai RoadSense",
        "status": "running",
        "docs": "/docs",
        "note": (
            "Prototype only; hazard reports are not verified "
            "road-safety data."
        ),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ============================================================
# AI MODEL — PREDICTION AND OPTIONAL HAZARD REPORTING
# ============================================================

_ai_predictor = None


def get_ai_predictor():
    """Load the trained model once, on the first AI request."""
    global _ai_predictor

    if _ai_predictor is None:
        if not MODEL_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Trained AI model not found at {MODEL_PATH}. "
                    "Run: python ml/train_model.py"
                ),
            )
        try:
            _ai_predictor = RoadSensePredictor(model_path=MODEL_PATH)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Could not load the RoadSense AI model: {exc}",
            ) from exc

    return _ai_predictor


def run_ai_prediction(
    features: dict[str, float],
    latitude: float,
    longitude: float,
    source_vehicle: str,
    should_report_hazard: bool,
    confidence_threshold: float,
):
    """Predict a road condition and optionally save it as a hazard."""
    predictor = get_ai_predictor()

    try:
        result = predictor.predict(features)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AI prediction failed: {exc}",
        ) from exc

    predicted_class = result["prediction"]
    confidence = float(result["confidence"])

    # The model's class name 'uneven_road' maps to the API's
    # existing hazard type 'uneven_surface'.
    event_type_map = {
        "pothole": "pothole",
        "bump": "bump",
        "uneven_road": "uneven_surface",
    }

    hazard_result = None
    is_hazard_class = predicted_class in event_type_map
    confidence_passed = confidence >= confidence_threshold

    if should_report_hazard and is_hazard_class and confidence_passed:
        report = HazardReport(
            event_type=event_type_map[predicted_class],
            latitude=latitude,
            longitude=longitude,
            confidence=confidence,
            source_vehicle=source_vehicle,
        )
        hazard_result = report_hazard(report)

    return {
        "prediction": predicted_class,
        "confidence": round(confidence, 4),
        "probabilities": {
            name: round(float(probability), 4)
            for name, probability in result["probabilities"].items()
        },
        "is_hazard": is_hazard_class,
        "confidence_threshold": confidence_threshold,
        "hazard_reported": hazard_result is not None,
        "hazard_report_result": hazard_result,
        "source_vehicle": source_vehicle,
        "coordinates": {"latitude": latitude, "longitude": longitude},
        "simulation_only": True,
        "note": (
            "This prototype prediction uses synthetic sensor data. "
            "It is not validated for real-world driving or safety decisions."
        ),
    }


@app.post("/api/ai/predict")
def ai_predict(request: AIPredictionRequest):
    """
    Predict from 30 named sensor features.
    A qualifying non-normal prediction can be saved as a hazard report.
    """
    return run_ai_prediction(
        features=request.features,
        latitude=request.latitude,
        longitude=request.longitude,
        source_vehicle=request.source_vehicle,
        should_report_hazard=request.report_hazard,
        confidence_threshold=request.confidence_threshold,
    )


@app.post("/api/ai/demo-predict")
def ai_demo_predict(request: DemoPredictionRequest):
    """
    Convenience endpoint for testing in /docs without typing 30 features.
    Selects one row from the generated synthetic CSV dataset.
    """
    if not DATASET_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Synthetic dataset not found at {DATASET_PATH}. "
                "Run: python simulation/generate_dataset.py"
            ),
        )

    try:
        dataset = pd.read_csv(DATASET_PATH)
        if "label" not in dataset.columns:
            raise ValueError("Dataset has no 'label' column.")

        rows = dataset[dataset["label"].astype(str) == request.sample_label]
        if rows.empty:
            raise ValueError(
                f"No sample found for label '{request.sample_label}'."
            )

        predictor = get_ai_predictor()
        missing = [
            name for name in predictor.feature_names
            if name not in dataset.columns
        ]
        if missing:
            raise ValueError(
                "Dataset is missing model features: " + ", ".join(missing)
            )

        sample = rows.iloc[0]
        features = {
            name: float(sample[name])
            for name in predictor.feature_names
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not prepare demo sample: {exc}",
        ) from exc

    result = run_ai_prediction(
        features=features,
        latitude=request.latitude,
        longitude=request.longitude,
        source_vehicle=request.source_vehicle,
        should_report_hazard=request.report_hazard,
        confidence_threshold=request.confidence_threshold,
    )
    result["expected_synthetic_label"] = request.sample_label
    return result


# ============================================================
# REPORT A HAZARD
# ============================================================

@app.post("/api/hazards", status_code=201)
def report_hazard(report: HazardReport):
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()

    with connect_db() as conn:
        recent = conn.execute(
            """
            SELECT id, latitude, longitude, reported_at
            FROM hazards
            WHERE event_type = ?
              AND status = 'active'
            ORDER BY id DESC
            LIMIT 100
            """,
            (report.event_type,),
        ).fetchall()

        for row in recent:
            try:
                reported_dt = datetime.fromisoformat(
                    row["reported_at"]
                )

                if reported_dt.tzinfo is None:
                    reported_dt = reported_dt.replace(
                        tzinfo=timezone.utc
                    )

                age_seconds = (
                    now_dt - reported_dt
                ).total_seconds()

            except (ValueError, TypeError):
                continue

            distance = haversine_m(
                report.latitude,
                report.longitude,
                row["latitude"],
                row["longitude"],
            )

            if 0 <= age_seconds <= 600 and distance <= 25:
                return {
                    "message": (
                        "Possible duplicate report; "
                        "existing hazard retained."
                    ),
                    "duplicate": True,
                    "hazard_id": row["id"],
                    "reported_at": row["reported_at"],
                }

        cur = conn.execute(
            """
            INSERT INTO hazards (
                event_type,
                latitude,
                longitude,
                confidence,
                source_vehicle,
                reported_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                report.event_type,
                report.latitude,
                report.longitude,
                report.confidence,
                report.source_vehicle,
                now,
            ),
        )

        conn.commit()
        hazard_id = cur.lastrowid

    return {
        "message": "Hazard report stored.",
        "duplicate": False,
        "hazard_id": hazard_id,
        "reported_at": now,
        "hazard": report.model_dump(),
    }


# ============================================================
# LIST HAZARDS
# ============================================================

@app.get("/api/hazards")
def list_hazards(
    limit: int = Query(default=100, ge=1, le=500),
):
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM hazards
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return {
        "count": len(rows),
        "hazards": [dict(row) for row in rows],
    }


# ============================================================
# FIND NEARBY HAZARDS
# ============================================================

@app.get("/api/hazards/nearby")
def nearby_hazards(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_m: float = Query(default=1000, gt=0, le=10000),
    max_age_hours: float = Query(default=24, gt=0, le=720),
):
    now = datetime.now(timezone.utc)

    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM hazards
            WHERE status = 'active'
            ORDER BY id DESC
            """
        ).fetchall()

    matches = []

    for row in rows:
        try:
            reported = datetime.fromisoformat(row["reported_at"])

            if reported.tzinfo is None:
                reported = reported.replace(tzinfo=timezone.utc)

            age_hours = (
                now - reported
            ).total_seconds() / 3600

        except (ValueError, TypeError):
            continue

        if age_hours < 0 or age_hours > max_age_hours:
            continue

        distance = haversine_m(
            latitude,
            longitude,
            row["latitude"],
            row["longitude"],
        )

        if distance <= radius_m:
            item = dict(row)
            item["distance_m"] = round(distance, 1)
            item["age_minutes"] = round(age_hours * 60, 1)
            matches.append(item)

    matches.sort(key=lambda item: item["distance_m"])

    return {
        "count": len(matches),
        "radius_m": radius_m,
        "hazards": matches,
    }


# ============================================================
# VEHICLE B: START SIMULATION
# ============================================================

@app.post("/api/simulation/vehicle-b/start")
def start_vehicle_b():
    """Start or restart the synthetic Vehicle B approach."""

    with vehicle_b_lock:
        vehicle_b_state["running"] = True

        vehicle_b_state["distance_from_hazard_m"] = (
            DEMO_START_DISTANCE_M
        )

        vehicle_b_state["speed_mps"] = DEMO_SPEED_MPS
        vehicle_b_state["last_updated"] = time.monotonic()

    return {
        "message": "Vehicle B simulation started.",
        "vehicle_id": "vehicle-B",
        "running": True,
        "distance_from_hazard_m": DEMO_START_DISTANCE_M,
        "speed_mps": DEMO_SPEED_MPS,
        "simulation_only": True,
    }


# ============================================================
# VEHICLE B: STOP SIMULATION
# ============================================================

@app.post("/api/simulation/vehicle-b/stop")
def stop_vehicle_b():
    with vehicle_b_lock:
        vehicle_b_state["running"] = False
        vehicle_b_state["last_updated"] = None

    return {
        "message": "Vehicle B simulation stopped.",
        "vehicle_id": "vehicle-B",
        "running": False,
        "simulation_only": True,
    }


# ============================================================
# VEHICLE B: GET WARNING STATE
# ============================================================

@app.get("/api/simulation/vehicle-b")
def get_vehicle_b_simulation():
    """
    Advance the synthetic vehicle according to elapsed time.

    The warning is illustrative and is not a real driving alert.
    """

    with vehicle_b_lock:
        if vehicle_b_state["running"]:
            current_time = time.monotonic()
            previous_time = vehicle_b_state["last_updated"]

            if previous_time is not None:
                elapsed_seconds = max(
                    0.0,
                    current_time - previous_time,
                )

                vehicle_b_state["distance_from_hazard_m"] -= (
                    vehicle_b_state["speed_mps"] * elapsed_seconds
                )

            vehicle_b_state["last_updated"] = current_time

        running = vehicle_b_state["running"]

        distance_m = vehicle_b_state[
            "distance_from_hazard_m"
        ]

        speed_mps = vehicle_b_state["speed_mps"]

    # Find an active database hazard close to the fixed demo point.
    nearby = nearby_hazards(
        latitude=DEMO_LATITUDE,
        longitude=DEMO_LONGITUDE,
        radius_m=1000,
        max_age_hours=24,
    )

    target_hazard = None

    for hazard in nearby["hazards"]:
        distance_from_demo_point = haversine_m(
            hazard["latitude"],
            hazard["longitude"],
            DEMO_LATITUDE,
            DEMO_LONGITUDE,
        )

        if distance_from_demo_point <= 25:
            target_hazard = hazard
            break

    # Default warning state.
    warning_level = "NONE"
    warning_message = "No immediate warning"

    passed_hazard = distance_m < 0

    if passed_hazard:
        warning_level = "PASSED"
        warning_message = "Hazard passed"

    elif target_hazard is None:
        warning_level = "NO_HAZARD"
        warning_message = (
            "No active hazard found at the demo location"
        )

    elif distance_m <= 30:
        warning_level = "CLOSE"
        warning_message = "HAZARD VERY CLOSE"

    elif distance_m <= 150:
        warning_level = "ADVANCE"
        warning_message = "ROAD HAZARD AHEAD"

    elif distance_m <= 300:
        warning_level = "APPROACHING"
        warning_message = "ROAD HAZARD APPROACHING"

    return {
        "vehicle_id": "vehicle-B",
        "running": running,
        "distance_from_hazard_m": max(round(distance_m, 1), 0),
        "speed_mps": speed_mps,
        "speed_kmh": round(speed_mps * 3.6, 1),
        "passed_hazard": passed_hazard,
        "warning_level": warning_level,
        "warning_message": warning_message,
        "hazard": target_hazard,
        "simulation_only": True,
    }


# ============================================================
# CLEAR HAZARDS — DEVELOPMENT ONLY
# ============================================================

@app.delete("/api/hazards")
def clear_hazards():
    """Development-only endpoint. Do not expose in production."""

    with connect_db() as conn:
        conn.execute("DELETE FROM hazards")
        conn.commit()

    return {"message": "All prototype hazards cleared."}

