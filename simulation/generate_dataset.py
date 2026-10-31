import csv
from pathlib import Path

import numpy as np

# Hyundai RoadSense synthetic sensor dataset generator.
# These are illustrative simulated readings, not real vehicle data.

RANDOM_SEED = 42
SAMPLE_RATE_HZ = 50
WINDOW_SECONDS = 2
SAMPLES_PER_WINDOW = SAMPLE_RATE_HZ * WINDOW_SECONDS
SAMPLES_PER_CLASS = 500

rng = np.random.default_rng(RANDOM_SEED)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "simulation" / "data" / "roadsense_sensor_dataset.csv"

CLASSES = ["normal", "pothole", "bump", "uneven_road"]


def generate_sample(road_condition):
    """Generate one synthetic six-axis sensor window."""
    t = np.arange(SAMPLES_PER_WINDOW) / SAMPLE_RATE_HZ

    # Simulated accelerometer readings in m/s^2.
    ax = rng.normal(0.0, 0.12, SAMPLES_PER_WINDOW)
    ay = rng.normal(0.0, 0.12, SAMPLES_PER_WINDOW)
    az = 9.81 + rng.normal(0.0, 0.18, SAMPLES_PER_WINDOW)

    # Simulated gyroscope readings in rad/s.
    gx = rng.normal(0.0, 0.025, SAMPLES_PER_WINDOW)
    gy = rng.normal(0.0, 0.025, SAMPLES_PER_WINDOW)
    gz = rng.normal(0.0, 0.025, SAMPLES_PER_WINDOW)

    if road_condition in ("pothole", "bump"):
        event_time = rng.uniform(0.5, 1.5)
        width = rng.uniform(0.035, 0.075)
        amplitude = rng.uniform(2.0, 5.0)
        pulse = np.exp(-0.5 * ((t - event_time) / width) ** 2)

        if road_condition == "pothole":
            az -= amplitude * pulse
            rebound_time = event_time + rng.uniform(0.08, 0.18)
            rebound_width = width * rng.uniform(1.0, 1.8)
            rebound = np.exp(
                -0.5 * ((t - rebound_time) / rebound_width) ** 2
            )
            az += amplitude * rng.uniform(0.4, 0.9) * rebound
        else:
            az += amplitude * pulse
            response_time = event_time + rng.uniform(0.08, 0.18)
            response_width = width * rng.uniform(1.0, 1.8)
            response = np.exp(
                -0.5 * ((t - response_time) / response_width) ** 2
            )
            az -= amplitude * rng.uniform(0.3, 0.8) * response

        gx += rng.normal(0.0, 0.10) * pulse
        gy += rng.normal(0.0, 0.10) * pulse

    elif road_condition == "uneven_road":
        frequency = rng.uniform(3.0, 8.0)
        phase = rng.uniform(0.0, 2.0 * np.pi)
        amplitude = rng.uniform(0.5, 1.5)
        vibration = amplitude * np.sin(2.0 * np.pi * frequency * t + phase)
        modulation_frequency = rng.uniform(0.3, 0.8)
        modulation = 0.65 + 0.35 * np.sin(
            2.0 * np.pi * modulation_frequency * t
        )
        vibration *= modulation
        az += vibration
        ax += 0.20 * vibration
        gx += 0.08 * vibration
        gy += 0.06 * vibration

    sensors = {
        "ax": ax, "ay": ay, "az": az,
        "gx": gx, "gy": gy, "gz": gz,
    }

    features = {}
    for axis, values in sensors.items():
        features[f"{axis}_mean"] = float(np.mean(values))
        features[f"{axis}_std"] = float(np.std(values))
        features[f"{axis}_min"] = float(np.min(values))
        features[f"{axis}_max"] = float(np.max(values))
        features[f"{axis}_rms"] = float(np.sqrt(np.mean(values ** 2)))

    features["label"] = road_condition
    return features


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    for road_condition in CLASSES:
        print(f"Generating samples for: {road_condition}")
        for _ in range(SAMPLES_PER_CLASS):
            rows.append(generate_sample(road_condition))

    rng.shuffle(rows)
    fieldnames = list(rows[0].keys())

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\nDataset generated successfully.")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Total samples: {len(rows)}")
    print(f"Features per sample: {len(fieldnames) - 1}")
    print(f"Sampling rate: {SAMPLE_RATE_HZ} Hz")
    print(f"Window duration: {WINDOW_SECONDS} seconds")
    print("\nClass distribution:")
    for road_condition in CLASSES:
        count = sum(row["label"] == road_condition for row in rows)
        print(f"  {road_condition}: {count}")


if __name__ == "__main__":
    main()
