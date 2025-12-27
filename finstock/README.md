# FinStock ML Prediction System

Hệ thống dự đoán cổ phiếu tăng giá >5% trong tuần tới sử dụng XGBoost.

## Cấu trúc

```
finstock/
├── back/                   # Backend API (FastAPI)
│   ├── database.py        # Database schema & connection
│   ├── etl_pipeline.py    # ETL tạo biến hàng tuần
│   ├── prediction_service.py  # ML prediction service
│   ├── main.py           # FastAPI endpoints
│   └── model/xgb_model.pkl  # Trained XGBoost model
├── front/                 # Frontend (Streamlit)
│   └── app.py            # Dashboard
└── uat/model/            # Jupyter notebooks (development)
```

## Setup

### 1. Install dependencies
```bash
cd finstock
pip install -r requirements.txt
```

### 2. Initialize database
```bash
cd back
python database.py
```

### 3. Run ETL (tạo biến hàng tuần)
```bash
python -c "
from etl_pipeline import WeeklyFeatureETL
import pandas as pd

# Load dữ liệu từ notebook
df = pd.read_parquet('uat/data/datafeat/2025-12-12/combine_feats_2025-12-12.parquet')

# Run ETL
etl = WeeklyFeatureETL(end_date='2025-12-12')
etl.run_pipeline(df)
"
```

### 4. Run predictions
```bash
python prediction_service.py
```

### 5. Start API
```bash
uvicorn back.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Start Dashboard
```bash
cd front
streamlit run app.py
```

## API Endpoints

- `GET /health` - Health check
- `GET /predictions/top?year=2025&quarter=4&top_n=10` - Top predictions
- `GET /predictions/ticker/{ticker}` - Predictions cho 1 ticker
- `GET /predictions/stats?year=2025&quarter=4` - Thống kê
- `POST /predictions/run?year=2025&quarter=4` - Chạy prediction

## Database Schema

**weekly_features**: Lưu features hàng tuần
- ticker, report_date, year, quarter
- features (JSONB)
- label_willgain_ov5pct

**weekly_predictions**: Lưu predictions
- ticker, report_date, year, quarter
- prediction_proba
- label_actual, model_version

**model_metadata**: Metadata của models
- model_version, model_path
- auc_score, train_date
- features_used, hyperparameters

## Quy trình hàng tuần

1. **Extract**: Lấy dữ liệu từ VNStock, YFinance
2. **Transform**: Tạo 300+ features, scaling, label
3. **Load**: Lưu vào database (weekly_features)
4. **Predict**: Load model → predict → lưu vào weekly_predictions
5. **Visualize**: Dashboard hiển thị top predictions

## Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
```
