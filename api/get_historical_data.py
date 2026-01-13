"""
API endpoint to fetch historical data from Neon PostgreSQL
Supports filtering by time period: 7d, 1m, 1y, all
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)

# Database connection
conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)

def get_date_filter(period):
    """Calculate start date based on period filter"""
    today = datetime.now()

    if period == '7d':
        return today - timedelta(days=7)
    elif period == '1m':
        return today - timedelta(days=30)
    elif period == '1y':
        return today - timedelta(days=365)
    else:  # 'all'
        return datetime(2000, 1, 1)

@app.route('/api/v1/gold', methods=['GET'])
def get_gold_data():
    """Get gold price historical data"""
    try:
        period = request.args.get('period', '1m')  # Default: 1 month
        start_date = get_date_filter(period)

        query = text("""
            SELECT date, buy_price, sell_price
            FROM vn_gold_24h_dojihn_hist
            WHERE date >= :start_date
            ORDER BY date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'start_date': start_date})

        # Convert to JSON-friendly format
        data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'buy_prices': df['buy_price'].tolist(),
            'sell_prices': df['sell_price'].tolist(),
            'count': len(df)
        }

        return jsonify({
            'success': True,
            'data': data,
            'period': period
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/silver', methods=['GET'])
def get_silver_data():
    """Get silver price historical data"""
    try:
        period = request.args.get('period', '1m')
        start_date = get_date_filter(period)

        query = text("""
            SELECT date, buy_price, sell_price
            FROM vn_silver_phuquy_hist
            WHERE date >= :start_date
            ORDER BY date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'start_date': start_date})

        data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'buy_prices': df['buy_price'].tolist(),
            'sell_prices': df['sell_price'].tolist(),
            'count': len(df)
        }

        return jsonify({
            'success': True,
            'data': data,
            'period': period
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/sbv-interbank', methods=['GET'])
def get_sbv_data():
    """Get SBV interbank rate historical data"""
    try:
        period = request.args.get('period', '1m')
        start_date = get_date_filter(period)

        query = text("""
            SELECT date, ls_quadem, ls_1w, ls_2w, ls_1m, ls_3m, ls_6m, ls_9m
            FROM vn_sbv_interbankrate
            WHERE date >= :start_date
            ORDER BY date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'start_date': start_date})

        data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'overnight': df['ls_quadem'].tolist(),
            'week_1': df['ls_1w'].tolist(),
            'week_2': df['ls_2w'].tolist(),
            'month_1': df['ls_1m'].tolist(),
            'month_3': df['ls_3m'].tolist(),
            'month_6': df['ls_6m'].tolist(),
            'month_9': df['ls_9m'].tolist(),
            'count': len(df)
        }

        return jsonify({
            'success': True,
            'data': data,
            'period': period
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/bank-termdepo', methods=['GET'])
def get_termdepo_data():
    """Get bank term deposit rates historical data"""
    try:
        period = request.args.get('period', '1m')
        bank_code = request.args.get('bank', 'ACB')  # Default: ACB
        start_date = get_date_filter(period)

        query = text("""
            SELECT date, term_1m, term_2m, term_3m, term_6m, term_9m,
                   term_12m, term_13m, term_18m, term_24m, term_36m
            FROM vn_bank_termdepo
            WHERE date >= :start_date AND bank_code = :bank_code
            ORDER BY date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'start_date': start_date, 'bank_code': bank_code})

        data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'term_1m': df['term_1m'].tolist(),
            'term_3m': df['term_3m'].tolist(),
            'term_6m': df['term_6m'].tolist(),
            'term_12m': df['term_12m'].tolist(),
            'count': len(df)
        }

        return jsonify({
            'success': True,
            'data': data,
            'period': period,
            'bank': bank_code
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/v1/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)