import os
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier

def train_and_save_models(csv_path="synthetic_crime_15k_cleaned.csv.xls", output_path="app/ml/crime_ml_bundle.joblib"):
    print(f"Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path)

    feature_cols = [c for c in df.columns if not c.startswith('label_')]
    X = df[feature_cols]

    y_syndicate = df['label_high_risk_cyber_syndicate']
    y_role = df['label_entity_role']
    y_bail = df['label_bail_or_custody_relief']
    y_conviction = df['label_conviction_outcome']

    print("Training 4 Machine Learning Forensics Classifiers...")
    
    rf_syndicate = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
    rf_syndicate.fit(X, y_syndicate)

    rf_role = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
    rf_role.fit(X, y_role)

    rf_bail = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
    rf_bail.fit(X, y_bail)

    rf_conviction = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
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
    print(f"Crime ML Bundle saved to {output_path} successfully!")

if __name__ == "__main__":
    train_and_save_models()