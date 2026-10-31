from pathlib import Path
import json
import sys

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "ml" / "models" / "roadsense_model.joblib"
DATASET_PATH = PROJECT_ROOT / "simulation" / "data" / "roadsense_sensor_dataset.csv"


class RoadSensePredictor:
    """Load the trained RoadSense model and predict from named sensor features."""

    def __init__(self, model_path: Path = MODEL_PATH):
        if not model_path.exists():
            raise FileNotFoundError(
                f"Trained model not found: {model_path}\n"
                "Run: python ml/train_model.py"
            )

        self.model = joblib.load(model_path)

        if not hasattr(self.model, "feature_names_in_"):
            raise ValueError(
                "The loaded model does not contain feature names. "
                "Retrain it using ml/train_model.py."
            )

        self.feature_names = list(self.model.feature_names_in_)
        self.classes = list(self.model.classes_)

    def predict(self, features: dict) -> dict:
        """Predict one sample. `features` must map feature names to numeric values."""
        missing = [name for name in self.feature_names if name not in features]
        if missing:
            raise ValueError(
                f"Missing {len(missing)} required feature(s): {', '.join(missing)}"
            )

        values = []
        for name in self.feature_names:
            try:
                value = float(features[name])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Feature '{name}' must be numeric.") from exc

            if not np.isfinite(value):
                raise ValueError(f"Feature '{name}' must be finite.")
            values.append(value)

        # Important: use a DataFrame with the same column names as training.
        # This avoids sklearn's "X does not have valid feature names" warning.
        input_data = pd.DataFrame([values], columns=self.feature_names)

        predicted_label = str(self.model.predict(input_data)[0])
        probabilities = self.model.predict_proba(input_data)[0]
        probability_by_class = {
            str(label): float(probability)
            for label, probability in zip(self.classes, probabilities)
        }

        return {
            "prediction": predicted_label,
            "confidence": probability_by_class[predicted_label],
            "probabilities": probability_by_class,
        }


def main() -> int:
    print("RoadSense AI prediction test")

    if not DATASET_PATH.exists():
        print(f"Dataset not found: {DATASET_PATH}", file=sys.stderr)
        print("Run: python simulation/generate_dataset.py", file=sys.stderr)
        return 1

    try:
        dataset = pd.read_csv(DATASET_PATH)
        if "label" not in dataset.columns:
            raise ValueError("Dataset must contain a 'label' column.")

        predictor = RoadSensePredictor()
        missing = [name for name in predictor.feature_names if name not in dataset.columns]
        if missing:
            raise ValueError(
                f"Dataset is missing model feature(s): {', '.join(missing)}"
            )

        # Select one synthetic pothole row if available; otherwise use the first row.
        pothole_rows = dataset[dataset["label"].astype(str) == "pothole"]
        sample = pothole_rows.iloc[0] if not pothole_rows.empty else dataset.iloc[0]
        expected_label = str(sample["label"])
        feature_values = {name: float(sample[name]) for name in predictor.feature_names}

        result = predictor.predict(feature_values)

        print(f"Expected synthetic label: {expected_label}")
        print(f"Predicted road condition: {result['prediction']}")
        print(f"Model confidence: {result['confidence']:.2%}")
        print("Class probabilities:")
        for label, probability in result["probabilities"].items():
            print(f"  {label}: {probability:.2%}")

        print("\nNote: this test uses synthetic data, not real vehicle sensor measurements.")
        return 0

    except Exception as exc:
        print(f"Prediction test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
