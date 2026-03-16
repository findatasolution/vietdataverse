from datetime import datetime, timedelta


def get_date_filter(period: str) -> str:
    now = datetime.now()
    if period == "7d":
        return (now - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "1m":
        return (now - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period == "1y":
        return (now - timedelta(days=365)).strftime("%Y-%m-%d")
    else:  # 'all'
        return "2000-01-01"
