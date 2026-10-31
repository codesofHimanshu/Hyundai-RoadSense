
"""
Hyundai RoadSense — Vehicle B Simulation

Simulates Vehicle B approaching hazards reported by Vehicle A.
Uses synthetic GPS coordinates and the RoadSense FastAPI backend.

All movement and warning thresholds are for demonstration only.
This is not a real navigation or vehicle safety system.
"""

import time
import requests


# ============================================================
# CONFIGURATION
# ============================================================

API_BASE_URL = "http://127.0.0.1:8000"

VEHICLE_ID = "vehicle-B"

# Demo hazard coordinates used by Vehicle A.
HAZARD_LATITUDE = 26.6337
HAZARD_LONGITUDE = 92.8000

# Vehicle B begins approximately 500 metres south of the hazard.
START_DISTANCE_M = 500.0

# Simulated speed: 36 km/h = 10 metres per second.
SPEED_MPS = 10.0

# Query nearby hazards within this radius.
SEARCH_RADIUS_M = 1000

# Simulate movement every two seconds.
UPDATE_INTERVAL_SECONDS = 2

# Illustrative warning thresholds (not safety-validated).
WARNING_DISTANCE_M = 300
ADVANCE_WARNING_DISTANCE_M = 150
CLOSE_WARNING_DISTANCE_M = 30

# Stop the simulation after Vehicle B passes the hazard.
STOP_AFTER_PASSING_M = 20


# ============================================================
# SYNTHETIC GPS
# ============================================================

def get_vehicle_position(distance_from_hazard_m):
    """
    Generate approximate GPS coordinates for Vehicle B.

    Positive distance means Vehicle B is south of the hazard.
    Negative distance means it has passed the hazard.

    This simplified model assumes a straight north/south route.
    """

    latitude = (
        HAZARD_LATITUDE
        - distance_from_hazard_m / 111_320
    )

    longitude = HAZARD_LONGITUDE

    return latitude, longitude


# ============================================================
# BACKEND CONNECTION
# ============================================================

def check_backend():
    """Check whether the FastAPI backend is available."""

    try:
        response = requests.get(
            f"{API_BASE_URL}/health",
            timeout=5,
        )

        response.raise_for_status()
        return True

    except requests.RequestException as error:
        print(f"\nBackend connection failed: {error}")
        print("Start FastAPI and try again.")
        return False


def get_nearby_hazards(latitude, longitude):
    """Retrieve nearby active hazards from the backend."""

    try:
        response = requests.get(
            f"{API_BASE_URL}/api/hazards/nearby",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "radius_m": SEARCH_RADIUS_M,
                "max_age_hours": 24,
            },
            timeout=5,
        )

        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        print(f"\nCould not retrieve hazards: {error}")
        return None


# ============================================================
# WARNING CLASSIFICATION
# ============================================================

def get_warning_level(distance_m):
    """
    Return a warning level based on the distance to a hazard.

    Thresholds are illustrative settings for the prototype.
    """

    if distance_m < 0:
        return None

    if distance_m > WARNING_DISTANCE_M:
        return None

    if distance_m > ADVANCE_WARNING_DISTANCE_M:
        return "HAZARD APPROACHING"

    if distance_m > CLOSE_WARNING_DISTANCE_M:
        return "ADVANCE WARNING"

    return "CLOSE HAZARD"


def show_driver_warning(hazard, distance_m, warning_level):
    """Print a driver-facing warning."""

    event_type = hazard.get(
        "event_type",
        "road hazard",
    )

    confidence = hazard.get("confidence", 0)

    messages = {
        "HAZARD APPROACHING":
            "A road hazard is reported ahead.",

        "ADVANCE WARNING":
            "Hazard ahead. Prepare to slow down when safe.",

        "CLOSE HAZARD":
            "Hazard very close. Slow down when safe.",
    }

    print("\n" + "!" * 55)
    print(f"ROADSENSE ALERT: {warning_level}")
    print(
        f"Hazard: {event_type.replace('_', ' ').title()}"
    )
    print(f"Distance: {distance_m:.1f} m")
    print(f"Reported confidence: {confidence * 100:.0f}%")
    print(messages[warning_level])
    print("Advisory only — drive safely.")
    print("!" * 55)


# ============================================================
# VEHICLE B SIMULATION
# ============================================================

def main():
    print("=" * 60)
    print("       HYUNDAI ROADSENSE - VEHICLE B")
    print("          SYNTHETIC GPS SIMULATION")
    print("=" * 60)

    print(f"\nVehicle ID: {VEHICLE_ID}")
    print(f"Backend: {API_BASE_URL}")
    print(f"Starting distance: {START_DISTANCE_M:.0f} m")
    print(f"Simulated speed: {SPEED_MPS * 3.6:.0f} km/h")
    print(f"Search radius: {SEARCH_RADIUS_M} m")

    print("\nChecking backend connection...")

    if not check_backend():
        return

    print("Backend connected.")

    distance_from_demo_hazard = START_DISTANCE_M

    # Remember the last warning level for each hazard.
    # This avoids printing the same warning every update.
    last_warning_levels = {}

    # Prevent the demo from generating warnings for hazards
    # behind the simulated vehicle.
    passed_demo_hazard = False

    while distance_from_demo_hazard >= -STOP_AFTER_PASSING_M:

        latitude, longitude = get_vehicle_position(
            distance_from_demo_hazard
        )

        print("\n" + "-" * 60)
        print(
            f"Vehicle B GPS: "
            f"{latitude:.6f}, {longitude:.6f}"
        )

        if distance_from_demo_hazard > 0:
            print(
                "Distance to demo hazard: "
                f"{distance_from_demo_hazard:.1f} m"
            )
        else:
            print(
                "Vehicle B has passed the demo hazard by "
                f"{abs(distance_from_demo_hazard):.1f} m"
            )

        # Retrieve hazard data from the backend.
        result = get_nearby_hazards(
            latitude,
            longitude,
        )

        if result is None:
            print("Hazard retrieval failed during this update.")

        else:
            hazards = result.get("hazards", [])

            print(
                "Hazards returned by backend: "
                f"{len(hazards)}"
            )

            if distance_from_demo_hazard <= 0:
                passed_demo_hazard = True

            for hazard in hazards:

                hazard_id = hazard.get("id")

                # Backend calculates geographic straight-line distance.
                hazard_distance = hazard.get("distance_m")

                if hazard_id is None or hazard_distance is None:
                    continue

                hazard_distance = float(hazard_distance)

                # This prototype has one known demo hazard.
                # Do not issue warnings after Vehicle B passes it.
                if passed_demo_hazard:
                    continue

                warning_level = get_warning_level(
                    hazard_distance
                )

                previous_level = last_warning_levels.get(
                    hazard_id
                )

                # Show a warning only when entering a new warning
                # zone or when the warning level changes.
                if (
                    warning_level is not None
                    and warning_level != previous_level
                ):
                    show_driver_warning(
                        hazard,
                        hazard_distance,
                        warning_level,
                    )

                # Remember the current level. None means that the
                # hazard is currently outside the warning zone.
                last_warning_levels[hazard_id] = warning_level

        if distance_from_demo_hazard <= -STOP_AFTER_PASSING_M:
            break

        time.sleep(UPDATE_INTERVAL_SECONDS)

        # Advance Vehicle B according to simulated speed and time.
        distance_from_demo_hazard -= (
            SPEED_MPS * UPDATE_INTERVAL_SECONDS
        )

    print("\n" + "=" * 60)
    print("Vehicle B simulation finished.")
    print("Synthetic GPS was used; no physical vehicle was involved.")
    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

