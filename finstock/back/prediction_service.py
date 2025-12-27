"""
Prediction Service
Load model và predict cho dữ liệu mới
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from sqlalchemy import text
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from back.database import SessionLocal

class PredictionService:
    """Service để load model và predict"""

    def __init__(self, model_path=None):
        """
        Args:
            model_path: Path to model file (default: back/model/xgb_model.pkl)
        """
        if model_path is None:
            model_path = Path(__file__).parent / "model" / "xgb_model.pkl"

        self.model_path = Path(model_path)
        self.model = None
        self.feature_names = None
        self._load_model()

    def _load_model(self):
        """Load XGBoost model"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found at {self.model_path}")

        print(f"Loading model from {self.model_path}")

        # XGBoost model được save bằng model.save_model()
        import xgboost as xgb
        self.model = xgb.Booster()
        self.model.load_model(str(self.model_path))

        # Lấy feature names từ model
        self.feature_names = self.model.feature_names
        print(f"Model loaded successfully with {len(self.feature_names)} features")

    def predict(self, features_df):
        """
        Predict probability cho dataframe features

        Args:
            features_df: DataFrame với các features

        Returns:
            predictions: Array of probabilities
        """
        # Đảm bảo đúng thứ tự features
        if self.feature_names:
            missing_features = set(self.feature_names) - set(features_df.columns)
            if missing_features:
                print(f"Warning: Missing features: {missing_features}")
                # Fill missing features với 0
                for feat in missing_features:
                    features_df[feat] = 0

            features_df = features_df[self.feature_names]

        # Convert to DMatrix
        import xgboost as xgb
        dmatrix = xgb.DMatrix(features_df)

        # Predict
        predictions = self.model.predict(dmatrix)
        return predictions

    def predict_from_db(self, year, quarter):
        """
        Load features từ database và predict

        Args:
            year: Năm
            quarter: Quý

        Returns:
            DataFrame với ticker, report_date, prediction_proba
        """
        print(f"Loading features from database for Q{quarter}/{year}...")

        with SessionLocal() as db:
            result = db.execute(text("""
                SELECT
                    ticker,
                    report_date,
                    year,
                    quarter,
                    features,
                    label_willgain_ov5pct
                FROM weekly_features
                WHERE year = :year AND quarter = :quarter
                ORDER BY ticker, report_date
            """), {'year': year, 'quarter': quarter})

            rows = result.fetchall()

        if not rows:
            print(f"No data found for Q{quarter}/{year}")
            return pd.DataFrame()

        # Parse features từ JSON
        data = []
        for row in rows:
            # Handle both string and dict
            if isinstance(row.features, str):
                features_dict = json.loads(row.features)
            else:
                features_dict = row.features
            features_dict['ticker'] = row.ticker
            features_dict['report_date'] = row.report_date
            features_dict['year'] = row.year
            features_dict['quarter'] = row.quarter
            features_dict['label_actual'] = row.label_willgain_ov5pct
            data.append(features_dict)

        df = pd.DataFrame(data)

        # Separate metadata và features
        metadata_cols = ['ticker', 'report_date', 'year', 'quarter', 'label_actual']
        feature_cols = [col for col in df.columns if col not in metadata_cols]

        # Predict
        predictions = self.predict(df[feature_cols])

        # Combine results
        result_df = df[metadata_cols].copy()
        result_df['prediction_proba'] = predictions

        print(f"Predicted {len(result_df)} records")
        return result_df

    def save_predictions_to_db(self, predictions_df, model_version="v1.0"):
        """
        Lưu predictions vào database

        Args:
            predictions_df: DataFrame with columns: ticker, report_date, year, quarter, prediction_proba, label_actual
            model_version: Version của model
        """
        print(f"Saving {len(predictions_df)} predictions to database...")

        with SessionLocal() as db:
            for idx, row in predictions_df.iterrows():
                db.execute(text("""
                    INSERT INTO weekly_predictions
                        (ticker, report_date, year, quarter, prediction_proba, label_actual, model_version)
                    VALUES
                        (:ticker, :report_date, :year, :quarter, :proba, :label, :version)
                    ON CONFLICT (ticker, report_date)
                    DO UPDATE SET
                        prediction_proba = EXCLUDED.prediction_proba,
                        label_actual = EXCLUDED.label_actual,
                        model_version = EXCLUDED.model_version
                """), {
                    'ticker': row['ticker'],
                    'report_date': row['report_date'],
                    'year': int(row['year']),
                    'quarter': int(row['quarter']),
                    'proba': float(row['prediction_proba']),
                    'label': int(row['label_actual']) if not pd.isna(row.get('label_actual')) else None,
                    'version': model_version
                })

            db.commit()
            print(f"Saved predictions to database successfully!")

    def get_top_predictions(self, year, quarter, top_n=10):
        """
        Lấy top N predictions từ database

        Args:
            year: Năm
            quarter: Quý
            top_n: Số lượng predictions

        Returns:
            DataFrame
        """
        with SessionLocal() as db:
            result = db.execute(text("""
                SELECT
                    ticker,
                    report_date,
                    year,
                    quarter,
                    prediction_proba,
                    label_actual,
                    model_version,
                    created_at
                FROM weekly_predictions
                WHERE year = :year AND quarter = :quarter
                ORDER BY prediction_proba DESC
                LIMIT :limit
            """), {'year': year, 'quarter': quarter, 'limit': top_n})

            rows = result.fetchall()

        df = pd.DataFrame(rows, columns=[
            'ticker', 'report_date', 'year', 'quarter',
            'prediction_proba', 'label_actual', 'model_version', 'created_at'
        ])

        return df


def run_weekly_prediction(year=None, quarter=None):
    """
    Chạy prediction cho một quý cụ thể
    Có thể schedule hàng tuần bằng cron job
    """
    if year is None or quarter is None:
        # Auto detect current quarter
        now = datetime.now()
        year = now.year
        quarter = (now.month - 1) // 3 + 1

    print(f"Running weekly prediction for Q{quarter}/{year}")
    print("=" * 60)

    # Initialize service
    service = PredictionService()

    # Predict
    predictions_df = service.predict_from_db(year, quarter)

    if len(predictions_df) > 0:
        # Save to database
        service.save_predictions_to_db(predictions_df, model_version="xgb_v1.0")

        # Show top 10
        print("\nTop 10 predictions:")
        print(predictions_df.nlargest(10, 'prediction_proba')[
            ['ticker', 'report_date', 'prediction_proba', 'label_actual']
        ])

    print("=" * 60)
    print("Weekly prediction completed!")


if __name__ == "__main__":
    # Test prediction service
    run_weekly_prediction(year=2025, quarter=4)
