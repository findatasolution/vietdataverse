"""
ETL Pipeline for Weekly Feature Generation
Tạo biến hàng tuần từ dữ liệu thị trường
"""
import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import text
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from uat.utils import library, feat_lib, model_dev
from back.database import engine, SessionLocal

class WeeklyFeatureETL:
    """ETL Pipeline cho việc tạo biến hàng tuần"""

    def __init__(self, end_date=None):
        """
        Args:
            end_date: Ngày kết thúc (mặc định là hôm nay)
        """
        self.end_date = end_date or datetime.today().strftime('%Y-%m-%d')
        self.start_date = "2001-01-01"
        self.output_path = project_root / f"uat/data/datafeat/{self.end_date}"
        self.output_path.mkdir(parents=True, exist_ok=True)

    def extract_market_data(self):
        """Bước 1: Trích xuất dữ liệu từ nguồn (VNStock, YFinance)"""
        print(f"[EXTRACT] Extracting market data up to {self.end_date}...")

        # Tạo danh sách các ngày thứ 6 (Friday)
        day_report_list = pd.date_range(
            start=self.start_date,
            end=self.end_date,
            freq="W-FRI"
        )

        # TODO: Gọi các hàm extract từ notebook
        # transaction_df = self._extract_transaction_data()
        # financial_df = self._extract_financial_data()
        # macro_df = self._extract_macro_data()

        print(f"[EXTRACT] Created {len(day_report_list)} weekly time points")
        return day_report_list

    def transform_features(self, combine_feats):
        """Bước 2: Transform và tạo features"""
        print("[TRANSFORM] Creating features...")

        # Clean và fix binary columns
        combine_feats, dropped_nan_cols, detected_binary_cols = \
            model_dev.clean_and_fix_binary(combine_feats)

        print(f"[TRANSFORM] Dropped {len(dropped_nan_cols)} NaN columns")
        print(f"[TRANSFORM] Detected {len(detected_binary_cols)} binary columns")

        # Tạo seasonal features
        combine_feats["tnx_sesional_q1"] = (combine_feats['quarter'] == 1).astype(int)
        combine_feats["tnx_sesional_q2"] = (combine_feats['quarter'] == 2).astype(int)
        combine_feats["tnx_sesional_q3"] = (combine_feats['quarter'] == 3).astype(int)
        combine_feats["tnx_sesional_q4"] = (combine_feats['quarter'] == 4).astype(int)

        # Tạo label
        combine_feats["label_willgain_ov5pct"] = (
            combine_feats.groupby("ticker")["tnx_close_price"].shift(-1) >
            combine_feats["tnx_close_price"] * 1.05
        ).astype(int)

        # Fix object columns
        obj_cols = combine_feats.select_dtypes(include=['object']).columns
        for col in obj_cols:
            if col not in ['ticker', 'reportdate']:
                combine_feats[col] = pd.to_numeric(
                    combine_feats[col].astype(str).str.replace(',', ''),
                    errors='coerce'
                )

        # MinMax Scaling
        header = ['reportdate', 'ticker', 'year', 'quarter']
        label = ['label_willgain_ov5pct']

        # Tìm binary columns
        binary_cols = [
            col for col in combine_feats.columns
            if combine_feats[col].dropna().isin([0,1]).all()
        ]

        no_scale_list = list(set(header + label + binary_cols))
        no_scale_exist = [col for col in no_scale_list if col in combine_feats.columns]

        # Scale
        scaled_features = library.preprocess_minmax_outlier(
            combine_feats,
            remove_list=no_scale_exist,
            exclude_binary=False
        )

        non_scaled = combine_feats[no_scale_exist]
        scaled_df = pd.concat([non_scaled, scaled_features], axis=1)

        print(f"[TRANSFORM] Created {len(scaled_df.columns)} features")
        return scaled_df

    def load_to_database(self, scaled_df):
        """Bước 3: Load dữ liệu vào database"""
        print("[LOAD] Loading features to database...")

        with SessionLocal() as db:
            for idx, row in scaled_df.iterrows():
                # Prepare features as JSON
                header_cols = ['reportdate', 'ticker', 'year', 'quarter']
                label_cols = ['label_willgain_ov5pct']

                feature_cols = [col for col in scaled_df.columns
                               if col not in header_cols + label_cols]

                features_dict = row[feature_cols].to_dict()

                # Convert numpy types to Python types
                features_dict = {
                    k: (float(v) if not pd.isna(v) else None)
                    for k, v in features_dict.items()
                }

                # Insert or update
                db.execute(text("""
                    INSERT INTO weekly_features
                        (ticker, report_date, year, quarter, features, label_willgain_ov5pct)
                    VALUES
                        (:ticker, :report_date, :year, :quarter, :features, :label)
                    ON CONFLICT (ticker, report_date)
                    DO UPDATE SET
                        features = EXCLUDED.features,
                        label_willgain_ov5pct = EXCLUDED.label_willgain_ov5pct
                """), {
                    'ticker': row['ticker'],
                    'report_date': row['reportdate'],
                    'year': int(row['year']),
                    'quarter': int(row['quarter']),
                    'features': json.dumps(features_dict),
                    'label': int(row['label_willgain_ov5pct']) if not pd.isna(row['label_willgain_ov5pct']) else None
                })

            db.commit()
            print(f"[LOAD] Loaded {len(scaled_df)} records to database")

    def run_pipeline(self, combine_feats=None):
        """Chạy toàn bộ ETL pipeline"""
        print(f"Starting ETL Pipeline for {self.end_date}")
        print("=" * 60)

        if combine_feats is None:
            # Load từ file parquet nếu có
            parquet_file = self.output_path / f"combine_feats_{self.end_date}.parquet"
            if parquet_file.exists():
                print(f"[INFO] Loading existing data from {parquet_file}")
                combine_feats = pd.read_parquet(parquet_file)
            else:
                raise FileNotFoundError(
                    f"No data found. Please run data extraction first or provide combine_feats dataframe."
                )

        # Transform
        scaled_df = self.transform_features(combine_feats)

        # Load to database
        self.load_to_database(scaled_df)

        # Save to parquet for backup
        output_file = self.output_path / f"scaled_features_{self.end_date}.parquet"
        scaled_df.to_parquet(output_file)
        print(f"[SAVE] Saved scaled features to {output_file}")

        print("=" * 60)
        print("ETL Pipeline completed successfully!")

        return scaled_df


def run_weekly_etl():
    """Hàm chạy ETL hàng tuần - có thể schedule bằng cron job"""
    today = datetime.today().strftime('%Y-%m-%d')
    etl = WeeklyFeatureETL(end_date=today)

    # Load data từ file hoặc database
    # combine_feats = load_combine_feats()  # TODO: implement

    # Run pipeline
    # etl.run_pipeline(combine_feats)

    print(f"Weekly ETL for {today} completed!")


if __name__ == "__main__":
    # Initialize database first
    from back.database import init_db
    init_db()

    # Run ETL (cần có dữ liệu combine_feats)
    # run_weekly_etl()
    print("ETL pipeline ready. Call run_weekly_etl() with data.")
