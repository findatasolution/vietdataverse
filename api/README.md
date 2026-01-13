# Viet Dataverse API

Flask API để cung cấp historical data từ Neon PostgreSQL cho charts trong Viet Dataverse.

## 📋 Endpoints

### Gold Price
```
GET /api/v1/gold?period={7d|1m|1y|all}
```
**Response:**
```json
{
  "success": true,
  "data": {
    "dates": ["2024-01-01", "2024-01-02", ...],
    "buy_prices": [80000000, 80100000, ...],
    "sell_prices": [80200000, 80300000, ...],
    "count": 30
  },
  "period": "1m"
}
```

### Silver Price
```
GET /api/v1/silver?period={7d|1m|1y|all}
```

### SBV Interbank Rates
```
GET /api/v1/sbv-interbank?period={7d|1m|1y|all}
```
**Response:**
```json
{
  "success": true,
  "data": {
    "dates": [...],
    "overnight": [...],
    "week_1": [...],
    "month_1": [...],
    "month_3": [...],
    "month_6": [...],
    "month_9": [...],
    "count": 30
  }
}
```

### Bank Term Deposit Rates
```
GET /api/v1/bank-termdepo?period={7d|1m|1y|all}&bank={ACB|VCB|...}
```

### Health Check
```
GET /api/v1/health
```

## 🚀 Installation & Running

### Local Development
```bash
cd api
pip install flask flask-cors sqlalchemy pandas psycopg2-binary

# Run server
python get_historical_data.py
```
Server sẽ chạy tại: `http://localhost:5000`

### Production Deployment
Deploy lên Heroku, Railway, hoặc cloud platform khác.

**Environment Variables:**
- `PORT`: Port number (default: 5000)
- Database connection string đã hardcoded trong code (nên chuyển sang env variable)

## 🔧 CORS Configuration

API đã enable CORS để frontend có thể gọi từ domain khác.

## 📊 Period Filters

- `7d`: Last 7 days
- `1m`: Last 30 days
- `1y`: Last 365 days
- `all`: All historical data

## ⚠️ Security Note

**QUAN TRỌNG:** Database connection string đang được hardcoded. Trong production, nên:
1. Move connection string vào environment variable
2. Sử dụng `.env` file với `python-dotenv`
3. Không commit `.env` vào Git

## 📦 Dependencies

```txt
flask==3.0.0
flask-cors==4.0.0
sqlalchemy==2.0.23
pandas==2.1.4
psycopg2-binary==2.9.9
```

## 🔗 Frontend Integration

Update `API_BASE_URL` trong `vietdataverse/index.html`:

```javascript
const API_BASE_URL = 'https://your-api-domain.com/api/v1';
```