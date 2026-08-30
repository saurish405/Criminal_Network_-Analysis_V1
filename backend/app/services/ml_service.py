import os
import joblib
import pandas as pd
from typing import Dict, Any

class MLForensicsService:
    def __init__(self, model_path: str = "app/ml/crime_ml_bundle.joblib"):
        self.bundle = None
        if os.path.exists(model_path):
            self.bundle = joblib.load(model_path)
            print(f"ML Forensics Models loaded successfully from {model_path}")
        else:
            print(f"Warning: {model_path} not found. Run python train_ml.py to enable ML inferences.")

    def predict_entity_intelligence(self, features: Dict[str, Any]) -> Dict[str, Any]:
        if not self.bundle:
            return {
                "ml_syndicate_probability": 0.5,
                "predicted_role": "Suspect",
                "conviction_propensity": 0.5,
                "bail_eligibility": "Pending Analysis"
            }

        feature_cols = self.bundle["feature_columns"]
        # Create zero-initialized row matching training schema
        input_data = {col: 0.0 for col in feature_cols}
        for k, v in features.items():
            if k in input_data:
                input_data[k] = float(v)

        df_input = pd.DataFrame([input_data])

        # 1. Syndicate Probability
        syndicate_prob = float(self.bundle["syndicate_model"].predict_proba(df_input)[0][1])

        # 2. Predicted Entity Role
        role_idx = int(self.bundle["role_model"].predict(df_input)[0])
        role_label = self.bundle["role_mapping"].get(role_idx, "Suspect")

        # 3. Conviction & Bail Propensities
        conviction_prob = float(self.bundle["conviction_model"].predict_proba(df_input)[0][1])
        bail_decision = "Eligible for Bail" if self.bundle["bail_model"].predict(df_input)[0] == 1 else "High Flight/Tamper Risk (Bail Opposed)"

        return {
            "ml_syndicate_probability": round(syndicate_prob, 4),
            "predicted_role": role_label,
            "conviction_propensity": round(conviction_prob, 4),
            "bail_eligibility": bail_decision
        }