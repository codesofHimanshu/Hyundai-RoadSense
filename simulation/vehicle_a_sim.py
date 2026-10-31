
"""
Hyundai RoadSense
Milestone 1: Synthetic Sensor Generator + Vehicle A

Generates synthetic accelerometer measurements, detects a simulated
road disturbance, and reports it to the existing FastAPI backend.

IMPORTANT:
- This uses synthetic data, not a physical sensor.
- The detector is a simple demonstration baseline.
- The reported location is simulated.
"""

import math
import random
import time
from datetime import datetime, timezone

import requests


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

API_BASE_URL = "http://127.0.0.1:8000"

# Simulated Vehicle A location.
# These are demonstration coordinates, not live GPS.
VEHICLE_A_LATITUDE = 26.6337
VEHICLE_A_LONGITUDE = 92.8000

VEHICLE_ID = "vehicle-A"

# Synthetic sensor configuration.
SAMPLE_RATE_HZ = 50
DURATION_SECONDS = 4

# Illustrative acceleration threshold in g.
# This value must be calibrated using real sensor data later.
IMPACT_THRESHOLD_G = 1.2

# Use a fixed seed for reproducible synthetic signals.
RANDOM_SEED = 42


# --------------------------------------------------
# SYNTHETIC SENSOR GENERATOR
# --------------------------------------------------

def generate_sensor_data(event_type="pothole"):
    """
    Generate synthetic three-axis accelerometer measurements.

    Values are illustrative and are not calibrated to a real vehicle.
    """

    random.seed(RANDOM_SEED)

    total_samples = SAMPLE_RATE_HZ * DURATION_SECONDS
    sensor_data = []

    # Generate the timestamp of the simulated disturbance.
    impact_index = total_samples // 2

    for i in range(total_samples):
        # Normal background variation.
        ax = random.gauss(0.0, 0.08)
        ay = random.gauss(0.0, 0.06)
        az = 1.0 + random.gauss(0.0, 0.08)

        # Insert a synthetic disturbance.
        if event_type == "pothole":
            offset = i - impact_index

            if offset == 0:
                az += 1.5
            elif offset == 1:
                az -= 0.8
            elif offset == 2:
                az += 0.4

        elif event_type == "bump":
            offset = i - impact_index

            if -2 <= offset <= 2:
                az += 0.7 if offset % 2 == 0 else -0.3

        elif event_type == "uneven_surface":
            if impact_index - 5 <= i <= impact_index + 5:
                ax += random.gauss(0.0, 0.3)
                az += random.gauss(0.0, 0.25)

        sensor_data.append({
            "sample": i,
            "timestamp_seconds": i / SAMPLE_RATE_HZ,
            "ax_g": ax,
            "ay_g": ay,
            "az_g": az,
        })

    return sensor_data


# --------------------------------------------------
# ROAD DISTURBANCE DETECTOR
# --------------------------------------------------

def detect_disturbance(sensor_data):
    """
    Basic rule-based detector for the simulated demonstration.

    It examines the deviation of vertical acceleration from 1 g.

    This is NOT a validated pothole classifier. Real-world detection
    requires sensor calibration, gravity/orientation handling,
    vehicle-motion filtering, and labeled real measurements.
    """

    maximum_deviation = 0.0
    event_sample = None

    for sample in sensor_data:
        deviation = abs(sample["az_g"] - 1.0)

        if deviation > maximum_deviation:
            maximum_deviation = deviation
            event_sample = sample

    detected = maximum_deviation >= IMPACT_THRESHOLD_G

    result = {
        "detected": detected,
        "maximum_deviation_g": round(maximum_deviation, 3),
        "event_sample": event_sample,
    }

    return result


# --------------------------------------------------
# REPORT TO FASTAPI
# --------------------------------------------------

def report_hazard(detection):
    """
    Send the simulated event to the existing POST /api/hazards endpoint.
    """

    if not detection["detected"]:
        print("\nNo disturbance detected.")
        print("Vehicle A will not report a hazard.")
        return

    payload = {
        "event_type": "pothole",
        "latitude": VEHICLE_A_LATITUDE,
        "longitude": VEHICLE_A_LONGITUDE,
        "confidence": 0.80,
        "source_vehicle": VEHICLE_ID,
    }

    endpoint = f"{API_BASE_URL}/api/hazards"

    print("\nSending hazard report to RoadSense backend...")

    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=5,
        )

        response.raise_for_status()

        result = response.json()

        print("\nHazard report response:")
        print(f"Message: {result.get('message', 'No message returned')}")
        print(f"Hazard ID: {result.get('hazard_id', 'Unknown')}")
        print(f"Duplicate report: {result.get('duplicate', 'Unknown')}")

    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to the RoadSense backend.")
        print("Make sure FastAPI is running at http://127.0.0.1:8000")

    except requests.exceptions.Timeout:
        print("\nERROR: The backend request timed out.")

    except requests.exceptions.HTTPError as error:
        print(f"\nERROR: The backend rejected the request: {error}")
        print(response.text)

    except requests.exceptions.RequestException as error:
        print(f"\nERROR: Request failed: {error}")


# --------------------------------------------------
# VEHICLE A SIMULATION
# --------------------------------------------------

def main():
    print("=" * 55)
    print("       HYUNDAI ROADSENSE - VEHICLE A")
    print("          SYNTHETIC SENSOR SIMULATION")
    print("=" * 55)

    print(f"\nVehicle ID: {VEHICLE_ID}")
    print(f"Simulated location: {VEHICLE_A_LATITUDE}, "
          f"{VEHICLE_A_LONGITUDE}")
    print(f"Sensor sampling rate: {SAMPLE_RATE_HZ} Hz")
    print(f"Simulation duration: {DURATION_SECONDS} seconds")

    print("\nGenerating synthetic accelerometer measurements...")
    sensor_data = generate_sensor_data("pothole")

    print(f"Generated samples: {len(sensor_data)}")

    print("\nRunning disturbance detector...")
    detection = detect_disturbance(sensor_data)

    print(f"Maximum vertical acceleration deviation: "
          f"{detection['maximum_deviation_g']} g")

    if detection["detected"]:
        print("\nSIMULATED DISTURBANCE DETECTED")
        print("Event type: Pothole-like impact")
        print("Source: Synthetic sensor data")
        print("Location: Simulated")
    else:
        print("\nNo disturbance detected.")

    report_hazard(detection)

    print("\nSimulation finished.")


if __name__ == "__main__":
    main()
