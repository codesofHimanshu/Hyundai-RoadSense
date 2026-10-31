
from pathlib import Path

import pandas as pd

from predict import RoadSensePredictor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "simulation" / "data" / "roadsense_sensor_dataset.csv"


def main():
    print("=" * 65)
    print("HYUNDAI ROADSENSE — AI MODEL DEMONSTRATION")
    print("=" * 65)

    if not DATASET_PATH.exists():
        print(f"Dataset not found: {DATASET_PATH}")
        return

    dataset = pd.read_csv(DATASET_PATH)
    predictor = RoadSensePredictor()

    print("\nModel loaded successfully.")
    print(f"Features: {len(predictor.feature_names)}")
    print(f"Classes: {', '.join(predictor.classes)}")

    print("\nFOUR-CLASS PREDICTION TEST")
    print("-" * 65)

    results = []

    # Select one synthetic sample from each class.
    for expected_label in ["normal", "pothole", "bump", "uneven_road"]:
        samples = dataset[dataset["label"] == expected_label]

        if samples.empty:
            print(f"No dataset sample found for: {expected_label}")
            continue

        sample = samples.iloc[0]

        features = {
            name: float(sample[name])
            for name in predictor.feature_names
        }

        result = predictor.predict(features)
        predicted_label = result["prediction"]
        confidence = result["confidence"]
        matches = predicted_label == expected_label

        results.append(matches)

        print(f"\nExpected class : {expected_label}")
        print(f"Predicted class: {predicted_label}")
        print(f"Confidence     : {confidence:.2%}")
        print(f"Sample match   : {'YES' if matches else 'NO'}")

    print("\n" + "=" * 65)
    print("DEMONSTRATION SUMMARY")
    print("=" * 65)

    if results:
        matches = sum(results)
        print(f"Samples tested: {len(results)}")
        print(f"Correct predictions: {matches}/{len(results)}")
        print(f"Sample match rate: {matches / len(results):.2%}")

    print(
        "\nNote: These are selected synthetic dataset samples. "
        "The sample match rate is not the model's test accuracy "
        "or evidence of real-world detection performance."
    )


if __name__ == "__main__":
    main()
