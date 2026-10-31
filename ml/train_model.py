import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

# Hyundai RoadSense - Random Forest training script.
# This evaluates performance on synthetic data only.

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = (
    PROJECT_ROOT / "simulation" / "data" / "roadsense_sensor_dataset.csv"
)
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
MODEL_PATH = MODEL_DIR / "roadsense_model.joblib"
METRICS_PATH = MODEL_DIR / "evaluation_metrics.json"

TARGET_COLUMN = "label"
TEST_SIZE = 0.20
RANDOM_STATE = 42


def main():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}\n"
            "Run: python simulation/generate_dataset.py"
        )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading synthetic sensor dataset...")
    dataset = pd.read_csv(DATASET_PATH)

    if dataset.empty:
        raise ValueError("The dataset is empty.")
    if TARGET_COLUMN not in dataset.columns:
        raise ValueError(f"Missing target column: {TARGET_COLUMN}")
    if dataset[TARGET_COLUMN].isna().any():
        raise ValueError("The dataset contains missing labels.")

    X = dataset.drop(columns=[TARGET_COLUMN])
    y = dataset[TARGET_COLUMN]

    if X.empty or len(X.columns) == 0:
        raise ValueError("No input features were found.")
    if not all(pd.api.types.is_numeric_dtype(X[c]) for c in X.columns):
        raise ValueError("All input features must be numeric.")
    if X.isna().any().any():
        raise ValueError("The dataset contains missing feature values.")

    print(f"Dataset samples: {len(dataset)}")
    print(f"Input features: {len(X.columns)}")
    print(f"Classes: {sorted(y.unique())}")
    print("\nSamples per class:")
    print(y.value_counts().sort_index().to_string())

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    print(f"\nTraining samples: {len(X_train)}")
    print(f"Testing samples: {len(X_test)}")
    print("\nTraining Random Forest classifier...")

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    labels = list(model.classes_)

    report_text = classification_report(
        y_test, predictions, labels=labels, zero_division=0
    )
    report_data = classification_report(
        y_test, predictions, labels=labels, output_dict=True, zero_division=0
    )
    matrix = confusion_matrix(y_test, predictions, labels=labels)

    print("\n" + "=" * 55)
    print("RANDOM FOREST EVALUATION")
    print("=" * 55)
    print(f"Test accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)")
    print("\nClassification report:")
    print(report_text)
    print("Confusion matrix (rows=actual, columns=predicted):")
    print("Class order:", labels)
    print(matrix)

    joblib.dump(model, MODEL_PATH)

    metrics = {
        "dataset": str(DATASET_PATH.relative_to(PROJECT_ROOT)),
        "total_samples": int(len(dataset)),
        "training_samples": int(len(X_train)),
        "testing_samples": int(len(X_test)),
        "feature_count": int(len(X.columns)),
        "classes": labels,
        "test_accuracy": float(accuracy),
        "classification_report": report_data,
        "confusion_matrix": matrix.tolist(),
        "confusion_matrix_class_order": labels,
        "model_type": "RandomForestClassifier",
        "warning": (
            "Synthetic-data evaluation only; this does not establish "
            "real-world road-hazard detection accuracy."
        ),
    }

    with METRICS_PATH.open("w", encoding="utf-8") as metrics_file:
        json.dump(metrics, metrics_file, indent=4)

    print("\nSaved trained model:")
    print(MODEL_PATH)
    print("\nSaved evaluation metrics:")
    print(METRICS_PATH)
    print("\nTraining and evaluation completed successfully.")


if __name__ == "__main__":
    main()
