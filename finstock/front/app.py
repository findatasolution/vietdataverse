"""
Streamlit Dashboard for FinStock Predictions
"""
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# API Configuration
API_BASE = "http://127.0.0.1:8000"  # Update cho production

# Page config
st.set_page_config(
    page_title="FinStock ML Predictions",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #667eea;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# =========================
# Helper Functions
# =========================
def call_api(endpoint, params=None):
    """Call API endpoint"""
    try:
        url = f"{API_BASE}{endpoint}"
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def format_proba(proba):
    """Format probability as percentage"""
    return f"{proba*100:.2f}%"

# =========================
# Main App
# =========================
def main():
    # Header
    st.markdown('<h1 class="main-header">📈 FinStock ML Predictions</h1>', unsafe_allow_html=True)
    st.markdown("Dự đoán cổ phiếu tăng giá > 5% trong tuần tới sử dụng XGBoost")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Cấu hình")

        # Health check
        health = call_api("/health")
        if health:
            st.success("✅ API Connected")
            st.metric("Total Predictions", health.get('total_predictions', 0))

            if not health.get('model_loaded', False):
                st.warning("⚠️ Model not loaded")
        else:
            st.error("❌ API Disconnected")

        st.divider()

        # Time filter
        st.subheader("📅 Chọn thời gian")
        current_year = datetime.now().year
        current_quarter = (datetime.now().month - 1) // 3 + 1

        year = st.selectbox(
            "Năm",
            options=list(range(2020, current_year + 1)),
            index=list(range(2020, current_year + 1)).index(current_year)
        )

        quarter = st.selectbox(
            "Quý",
            options=[1, 2, 3, 4],
            index=current_quarter - 1
        )

        top_n = st.slider("Số lượng hiển thị", 5, 50, 20)

        st.divider()

        # Actions
        if st.button("🔄 Chạy Prediction"):
            with st.spinner("Đang chạy prediction..."):
                try:
                    response = requests.post(
                        f"{API_BASE}/predictions/run",
                        params={'year': year, 'quarter': quarter},
                        timeout=30
                    )

                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ {result.get('message')}")
                        st.metric("Total", result.get('total_predictions'))
                    else:
                        st.error(f"Error {response.status_code}: {response.text[:200]}")
                except Exception as e:
                    st.error(f"API Error: {str(e)}")

    # =========================
    # Main Content
    # =========================

    # Statistics
    st.header(f"📊 Thống kê Q{quarter}/{year}")

    stats = call_api("/predictions/stats", params={'year': year, 'quarter': quarter})

    if stats:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Tổng Predictions",
                stats.get('total_predictions', 0)
            )

        with col2:
            st.metric(
                "Avg Probability",
                format_proba(stats.get('avg_probability', 0))
            )

        with col3:
            st.metric(
                "Actual Gains",
                stats.get('actual_gains', 0)
            )

        with col4:
            gain_rate = stats.get('gain_rate', 0)
            st.metric(
                "Gain Rate",
                format_proba(gain_rate),
                delta=f"{(gain_rate - 0.5)*100:.1f}% vs baseline" if gain_rate else None
            )

    st.divider()

    # Top Predictions
    st.header(f"🎯 Top {top_n} Predictions")

    predictions = call_api(
        "/predictions/top",
        params={'year': year, 'quarter': quarter, 'top_n': top_n}
    )

    if predictions and len(predictions) > 0:
        # Convert to DataFrame
        df = pd.DataFrame(predictions)

        # Display table
        st.dataframe(
            df[['ticker', 'report_date', 'prediction_proba', 'label_actual']].style.format({
                'prediction_proba': '{:.2%}',
                'report_date': lambda x: x
            }).background_gradient(subset=['prediction_proba'], cmap='RdYlGn'),
            use_container_width=True,
            height=400
        )

        # Visualization
        col1, col2 = st.columns(2)

        with col1:
            # Bar chart
            fig = px.bar(
                df.head(20),
                x='ticker',
                y='prediction_proba',
                title=f'Top 20 Tickers - Prediction Probability',
                color='prediction_proba',
                color_continuous_scale='RdYlGn'
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Distribution
            fig = px.histogram(
                df,
                x='prediction_proba',
                nbins=30,
                title='Phân phối Prediction Probability',
                color_discrete_sequence=['#667eea']
            )
            st.plotly_chart(fig, use_container_width=True)

        # Download button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f'predictions_Q{quarter}_{year}.csv',
            mime='text/csv',
        )

    else:
        st.info(f"Không có dữ liệu cho Q{quarter}/{year}. Hãy chạy prediction trước.")

    st.divider()

    # Search by ticker
    st.header("🔍 Tìm kiếm theo Ticker")

    col1, col2 = st.columns([3, 1])

    with col1:
        ticker_search = st.text_input(
            "Nhập mã cổ phiếu",
            placeholder="VD: ACB, VCB, HPG..."
        ).upper()

    with col2:
        search_limit = st.number_input("Số records", 5, 50, 10)

    if ticker_search:
        ticker_data = call_api(
            f"/predictions/ticker/{ticker_search}",
            params={'limit': search_limit}
        )

        if ticker_data:
            ticker_df = pd.DataFrame(ticker_data)

            st.subheader(f"Predictions cho {ticker_search}")
            st.dataframe(
                ticker_df.style.format({
                    'prediction_proba': '{:.2%}'
                }).background_gradient(subset=['prediction_proba'], cmap='RdYlGn'),
                use_container_width=True
            )

            # Time series chart
            ticker_df['report_date'] = pd.to_datetime(ticker_df['report_date'])
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=ticker_df['report_date'],
                y=ticker_df['prediction_proba'],
                mode='lines+markers',
                name='Prediction',
                line=dict(color='#667eea', width=2)
            ))

            fig.update_layout(
                title=f'{ticker_search} - Prediction Probability Over Time',
                xaxis_title='Date',
                yaxis_title='Probability',
                yaxis_tickformat='.0%'
            )

            st.plotly_chart(fig, use_container_width=True)

    # Footer
    st.divider()
    st.caption("© 2025 FinStock ML System | Powered by XGBoost & Streamlit")


if __name__ == "__main__":
    main()
