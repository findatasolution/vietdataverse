# import os
# import logging
# import pandas as pd
# from sqlalchemy import create_engine
# from back.role_access import get_user_bu

# logger = logging.getLogger(__name__)

# def get_db_engine():
#     """Get SQLAlchemy engine for database queries"""
#     CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB")
#     if not CRAWLING_BOT_DB:
#         return None
#     return create_engine(CRAWLING_BOT_DB)


# def query_historical_pl(role: str, user_email: str = None):
#     """
#     Query historical P&L data based on user role

#     GCEO: Aggregated by BU, category, period
#     BUGM: Detailed data filtered by assigned BU

#     Returns formatted context string for LLM (OPTIMIZED - Summary only)
#     """
#     try:
#         engine = get_db_engine()
#         if not engine:
#             return "Database not configured"

#         if role == "gceo":
#             # Group CEO - Aggregated strategic view across all BUs (LIMIT 30)
#             query = """
#             SELECT
#                 business_unit,
#                 category,
#                 TO_CHAR(date, 'YYYY-MM') as period,
#                 SUM(amount) as total_amount
#             FROM financial_pl
#             WHERE actual_budget = 'Actual'
#             GROUP BY business_unit, category, TO_CHAR(date, 'YYYY-MM')
#             ORDER BY period DESC, business_unit, category
#             LIMIT 30
#             """
#         elif role == "bugm":
#             # BU General Manager - Summary by category and period (OPTIMIZED)
#             user_bu = get_user_bu(user_email) if user_email else None
#             if not user_bu:
#                 return "No Business Unit assigned. Contact administrator."

#             query = f"""
#             SELECT
#                 TO_CHAR(date, 'YYYY-MM') as period,
#                 category,
#                 subcategory,
#                 SUM(amount) as total_amount,
#                 COUNT(*) as line_items
#             FROM financial_pl
#             WHERE actual_budget = 'Actual'
#               AND business_unit = '{user_bu}'
#             GROUP BY TO_CHAR(date, 'YYYY-MM'), category, subcategory
#             ORDER BY period DESC, category
#             LIMIT 50
#             """
#         else:
#             return "Invalid role. Access denied."

#         df = pd.read_sql(query, engine)

#         if len(df) == 0:
#             return "No historical data available"

#         # Format for LLM (COMPACT)
#         if role == "gceo":
#             context = f"""P&L DATA (Aggregated, Latest 3 months):
# {df.to_string(index=False, max_rows=30)}
# """
#         else:  # bugm
#             user_bu = get_user_bu(user_email)
#             context = f"""P&L DATA ({user_bu}, Summary by Category):
# {df.to_string(index=False, max_rows=50)}
# """

#         return context

#     except Exception as e:
#         logger.error(f"Query error: {e}")
#         return f"Error loading historical data: {str(e)}"


# def query_balance_sheet(role: str, user_email: str = None):
#     """Query balance sheet data based on role (DISABLED to save tokens)"""
#     return ""  # Disabled - only provide if user explicitly asks


# def query_cash_flow(role: str, user_email: str = None):
#     """Query cash flow data based on role (DISABLED to save tokens)"""
#     return ""  # Disabled - only provide if user explicitly asks


# def get_all_historical_context(role: str, user_email: str = None):
#     """
#     Get all historical financial context for AI

#     GCEO: Aggregated strategic view of all BUs
#     BUGM: Detailed view of assigned BU only
#     """
#     if role not in ["gceo", "bugm"]:
#         return "Invalid role. No access to historical data."

#     context = query_historical_pl(role, user_email)
#     context += query_balance_sheet(role, user_email)
#     context += query_cash_flow(role, user_email)

#     # Calculate and add financial metrics from the data (OPTIMIZED - compact format)
#     try:
#         engine = get_db_engine()
#         if engine:
#             # Get actual P&L data for metrics calculation
#             query = """
#             SELECT category, SUM(amount) as amount
#             FROM financial_pl
#             WHERE actual_budget = 'Actual'
#             GROUP BY category
#             """
#             df = pd.read_sql(query, engine)

#             if len(df) > 0:
#                 # Import calculate function
#                 from back.financial_knowledge import calculate_financial_metrics
#                 metrics = calculate_financial_metrics(df)

#                 # Format metrics for AI (COMPACT - one line each)
#                 context += "\nKEY METRICS:\n"
#                 context += f"Revenue: ${metrics.get('total_revenue', 0)/1e6:.1f}M | "
#                 context += f"COGS: ${metrics.get('total_cogs', 0)/1e6:.1f}M | "
#                 context += f"OpEx: ${metrics.get('total_opex', 0)/1e6:.1f}M\n"
#                 context += f"GP: ${metrics.get('gross_profit', 0)/1e6:.1f}M ({metrics.get('gross_margin', 0):.1f}%) | "
#                 context += f"OpIncome: ${metrics.get('operating_income', 0)/1e6:.1f}M ({metrics.get('operating_margin', 0):.1f}%)\n"
#     except Exception as e:
#         logger.error(f"Error calculating metrics: {e}")

#     return context
