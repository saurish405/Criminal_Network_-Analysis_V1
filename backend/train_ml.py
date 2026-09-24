import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

def train_and_save_models(csv_path="synthetic_crime_15k_cleaned.csv", output_path="app/ml/crime_ml_bundle.joblib"):
    print(f"Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path)

    label_cols = [
        'label_high_risk_cyber_syndicate',
        'label_entity_role',
        'label_bail_or_custody_relief',
        'label_conviction_outcome'
    ]

    feature_cols = [c for c in df.columns if c not in label_cols]
    X = df[feature_cols]

    y_syndicate = df['label_high_risk_cyber_syndicate']
    y_role = df['label_entity_role']
    y_bail = df['label_bail_or_custody_relief']
    y_conviction = df['label_conviction_outcome']

    print(f"Training on {len(X)} records across {len(feature_cols)} features...")

    rf_syndicate = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf_syndicate.fit(X, y_syndicate)

    rf_role = RandomForestClassifier(
        n_estimators=100,
        max_depth=14,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf_role.fit(X, y_role)

    rf_bail = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf_bail.fit(X, y_bail)

    rf_conviction = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf_conviction.fit(X, y_conviction)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    bundle = {
        "feature_columns": feature_cols,
        "syndicate_model": rf_syndicate,
        "role_model": rf_role,
        "bail_model": rf_bail,
        "conviction_model": rf_conviction,
        "role_mapping": {
            0: "Low-Level Associate",
            1: "Syndicate Kingpin / Mastermind",
            2: "Peripheral Suspect",
            3: "Logistics & Arms Smuggler",
            4: "Central Mule & Hawala Manager",
            5: "Fake Call Center / Vishing Operator"
        }
    }

    joblib.dump(bundle, output_path)
    print(f"Saved balanced ML bundle to {output_path} successfully!")

if __name__ == "__main__":
    train_and_save_models()