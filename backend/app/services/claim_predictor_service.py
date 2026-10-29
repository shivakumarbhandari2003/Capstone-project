import threading
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
import joblib
import pandas as pd
from fastapi import HTTPException, status
from backend.app.core.config import settings
from backend.app.core.logging_config import logger
from backend.app.api.schemas.claim_predictor import ClaimPredictionInput

class ClaimPredictorService:
    """
    Singleton service encapsulating the trained insurance claim prediction model.
    Loads 'insurance_claim_model.pkl' and 'feature_columns.pkl' once at initialization.
    Applies exact preprocessing, one-hot alignment, and prediction logic established in claim_predictor_package/app.py.
    """

    def __init__(self, package_dir: Optional[Path] = None):
        self.package_dir = package_dir or (settings.BASE_DIR / "claim_predictor_package")
        self.model_path = self.package_dir / "insurance_claim_model.pkl"
        self.features_path = self.package_dir / "feature_columns.pkl"
        self._model = None
        self._expected_features = None
        self._lock = threading.Lock()
        self._load_model_artifacts()

    def _load_model_artifacts(self):
        """Loads model and feature column definitions once into memory."""
        try:
            if not self.model_path.exists():
                logger.error(f"Claim predictor model artifact missing at '{self.model_path}'.")
                return

            self._model = joblib.load(self.model_path)
            if hasattr(self._model, "feature_names_in_"):
                self._expected_features = list(self._model.feature_names_in_)
            elif self.features_path.exists():
                self._expected_features = joblib.load(self.features_path)
            else:
                logger.warning("Feature column names not found in model or feature_columns.pkl.")
            
            logger.info(f"ClaimPredictorService initialized with {len(self._expected_features or [])} expected features.")
        except Exception as e:
            logger.error(f"Failed to load Claim Predictor model artifacts: {e}", exc_info=True)
            self._model = None
            self._expected_features = None

    def predict(self, input_data: ClaimPredictionInput) -> Dict[str, Any]:
        """
        Executes prediction on validated input data matching app.py logic:
        1. Construct raw DataFrame
        2. pd.get_dummies
        3. reindex with expected features (fill_value=0)
        4. model.predict and bound at 0
        """
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._load_model_artifacts()

        if self._model is None or not self._expected_features:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Insurance Claim Predictor model is currently unavailable on this server."
            )

        try:
            # 1. Construct raw input DataFrame exactly as in app.py
            raw_input = pd.DataFrame({
                "age": [input_data.age],
                "days_hospitalised": [input_data.days_hospitalised],
                "icu_days": [input_data.icu_days],
                "procedures_claimed": [input_data.procedures_claimed],
                "prior_daycare_claims_year": [input_data.prior_daycare_claims_year],
                "extended_stay_flag": [input_data.extended_stay_flag],
                "plan": [input_data.plan],
                "pre_existing": [input_data.pre_existing],
                "claim_type": [input_data.claim_type],
                "documents_complete": [input_data.documents_complete],
            })

            # 2. One-hot encoding and feature column realignment
            encoded_input = pd.get_dummies(raw_input)
            final_input = encoded_input.reindex(columns=self._expected_features, fill_value=0)

            # 3. Model inference
            raw_prediction = float(self._model.predict(final_input)[0])
            bounded_prediction = max(0.0, raw_prediction)

            request_id = f"pred_{uuid.uuid4().hex[:12]}"
            formatted_val = f"Rs. {bounded_prediction:,.2f}"

            logger.info(f"[{request_id}] Claim prediction generated: {bounded_prediction:.2f} (Rs. {bounded_prediction:,.2f})")

            return {
                "request_id": request_id,
                "prediction": round(bounded_prediction, 2),
                "formatted_prediction": formatted_val,
                "output_units": "INR (Rs.)",
                "validated_inputs": input_data.model_dump()
            }
        except Exception as e:
            logger.error(f"Error during claim prediction calculation: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Claim prediction inference failed: {str(e)}"
            )

# Global singleton instance
claim_predictor_service = ClaimPredictorService()
