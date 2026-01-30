# # financial_knowledge.py
# # Financial Glossary, Formulas, and Domain Knowledge for AI

# FINANCIAL_GLOSSARY = {
#     # Income Statement / P&L Terms
#     "revenue": "Total income generated from business operations before any expenses",
#     "gross_revenue": "Total revenue before deductions",
#     "net_revenue": "Revenue after returns, allowances, and discounts",
#     "cogs": "Cost of Goods Sold - Direct costs of producing goods/services sold",
#     "gross_profit": "Revenue minus Cost of Goods Sold",
#     "gross_margin": "Gross profit as a percentage of revenue",

#     # Operating Expenses
#     "opex": "Operating Expenses - Ongoing costs to run the business",
#     "operating_expenses": "Costs incurred during normal business operations (salaries, rent, utilities)",
#     "sg&a": "Selling, General & Administrative expenses",
#     "r&d": "Research and Development expenses",

#     # Profitability Metrics
#     "ebit": "Earnings Before Interest and Taxes - Operating profit",
#     "ebitda": "Earnings Before Interest, Taxes, Depreciation, and Amortization",
#     "operating_income": "Profit from operations (Revenue - COGS - OpEx)",
#     "net_income": "Bottom line profit after all expenses, taxes, and interest",
#     "net_profit_margin": "Net income as a percentage of revenue",

#     # Capital Expenditure
#     "capex": "Capital Expenditures - Money spent on fixed assets (equipment, buildings)",
#     "depreciation": "Systematic allocation of cost of tangible assets over useful life",
#     "amortization": "Gradual write-off of intangible assets or debt",

#     # Return Metrics
#     "roi": "Return on Investment - (Gain - Cost) / Cost * 100%",
#     "roa": "Return on Assets - Net Income / Total Assets",
#     "roe": "Return on Equity - Net Income / Shareholder Equity",
#     "roic": "Return on Invested Capital",

#     # Cash Flow
#     "cash_flow": "Movement of money in and out of business",
#     "operating_cash_flow": "Cash generated from normal business operations",
#     "free_cash_flow": "Operating cash flow minus capital expenditures",
#     "fcf": "Free Cash Flow - Cash available after maintaining/expanding asset base",
#     "working_capital": "Current Assets minus Current Liabilities",

#     # Balance Sheet
#     "assets": "Resources owned by the company with economic value",
#     "current_assets": "Assets expected to convert to cash within one year",
#     "fixed_assets": "Long-term tangible assets (property, equipment)",
#     "liabilities": "Financial obligations and debts owed",
#     "current_liabilities": "Debts due within one year",
#     "equity": "Residual ownership interest (Assets - Liabilities)",
#     "shareholders_equity": "Net worth belonging to shareholders",

#     # Variance Analysis
#     "variance": "Difference between actual and budgeted/expected amounts",
#     "favorable_variance": "Actual results better than budget (revenue higher, costs lower)",
#     "unfavorable_variance": "Actual results worse than budget",
#     "variance_percentage": "(Actual - Budget) / Budget * 100%",

#     # Financial Ratios
#     "current_ratio": "Current Assets / Current Liabilities (liquidity measure)",
#     "quick_ratio": "(Current Assets - Inventory) / Current Liabilities",
#     "debt_to_equity": "Total Debt / Total Equity",
#     "debt_ratio": "Total Debt / Total Assets",

#     # Performance Metrics
#     "kpi": "Key Performance Indicator - Measurable value showing effectiveness",
#     "burn_rate": "Rate at which company spends cash (typically monthly)",
#     "runway": "Months of operation remaining based on current cash and burn rate",
#     "arr": "Annual Recurring Revenue",
#     "mrr": "Monthly Recurring Revenue",

#     # Forecasting
#     "forecast": "Prediction of future financial performance",
#     "projection": "Estimated future financial results",
#     "budget": "Financial plan for a defined period",
#     "yoy": "Year-over-Year comparison",
#     "qoq": "Quarter-over-Quarter comparison",
#     "mom": "Month-over-Month comparison",
# }

# FINANCIAL_FORMULAS = {
#     "gross_profit": {
#         "formula": "Revenue - Cost of Goods Sold",
#         "example": "If Revenue = $1,000,000 and COGS = $600,000, Gross Profit = $400,000"
#     },
#     "gross_margin": {
#         "formula": "(Gross Profit / Revenue) × 100%",
#         "example": "If Gross Profit = $400,000 and Revenue = $1,000,000, Margin = 40%"
#     },
#     "ebitda": {
#         "formula": "Net Income + Interest + Taxes + Depreciation + Amortization",
#         "alternative": "Operating Income + Depreciation + Amortization",
#         "example": "If Operating Income = $200k, Depreciation = $50k, Amortization = $10k, EBITDA = $260k"
#     },
#     "operating_margin": {
#         "formula": "(Operating Income / Revenue) × 100%",
#         "example": "If Operating Income = $200,000 and Revenue = $1,000,000, Operating Margin = 20%"
#     },
#     "net_profit_margin": {
#         "formula": "(Net Income / Revenue) × 100%",
#         "example": "If Net Income = $150,000 and Revenue = $1,000,000, Net Margin = 15%"
#     },
#     "roi": {
#         "formula": "((Gain from Investment - Cost of Investment) / Cost of Investment) × 100%",
#         "example": "Invested $100k, returned $150k: ROI = ($150k - $100k) / $100k = 50%"
#     },
#     "roa": {
#         "formula": "(Net Income / Total Assets) × 100%",
#         "example": "Net Income = $500k, Total Assets = $5M, ROA = 10%"
#     },
#     "roe": {
#         "formula": "(Net Income / Shareholders' Equity) × 100%",
#         "example": "Net Income = $500k, Equity = $2M, ROE = 25%"
#     },
#     "current_ratio": {
#         "formula": "Current Assets / Current Liabilities",
#         "interpretation": ">1 = Good liquidity, <1 = Potential liquidity issues",
#         "example": "Current Assets = $500k, Current Liabilities = $300k, Ratio = 1.67"
#     },
#     "quick_ratio": {
#         "formula": "(Current Assets - Inventory) / Current Liabilities",
#         "interpretation": "More conservative liquidity measure",
#         "example": "Current Assets = $500k, Inventory = $150k, Current Liab = $300k, Ratio = 1.17"
#     },
#     "debt_to_equity": {
#         "formula": "Total Debt / Total Equity",
#         "interpretation": "<1 = Less leveraged, >2 = Highly leveraged",
#         "example": "Total Debt = $800k, Total Equity = $1.2M, Ratio = 0.67"
#     },
#     "working_capital": {
#         "formula": "Current Assets - Current Liabilities",
#         "example": "Current Assets = $500k, Current Liabilities = $300k, Working Capital = $200k"
#     },
#     "free_cash_flow": {
#         "formula": "Operating Cash Flow - Capital Expenditures",
#         "example": "Operating CF = $800k, CapEx = $200k, FCF = $600k"
#     },
#     "burn_rate": {
#         "formula": "Cash at Beginning - Cash at End / Number of Months",
#         "example": "Started with $1.2M, ended with $900k after 3 months: Burn = $100k/month"
#     },
#     "runway": {
#         "formula": "Current Cash Balance / Monthly Burn Rate",
#         "example": "Cash = $1.2M, Burn = $100k/month, Runway = 12 months"
#     },
#     "variance": {
#         "formula": "Actual - Budget",
#         "variance_percentage": "((Actual - Budget) / Budget) × 100%",
#         "example": "Actual Revenue = $1.1M, Budget = $1M, Variance = +$100k (+10%)"
#     }
# }

# FINANCIAL_ANALYSIS_PROMPTS = {
#     "revenue_analysis": """
# Analyze revenue performance by:
# 1. Total revenue comparison (actual vs budget)
# 2. Revenue breakdown by category/product line
# 3. Revenue trends over time
# 4. Regional/BU performance
# 5. Key drivers of revenue changes
# """,
#     "profitability_analysis": """
# Assess profitability through:
# 1. Gross margin trends
# 2. Operating margin analysis
# 3. EBITDA calculation and trends
# 4. Net profit margin evolution
# 5. Margin compression/expansion factors
# """,
#     "variance_analysis": """
# Conduct variance analysis by:
# 1. Identifying significant variances (>10% or >$X threshold)
# 2. Categorizing as favorable or unfavorable
# 3. Calculating variance percentages
# 4. Explaining root causes
# 5. Recommending corrective actions
# """,
#     "cash_flow_analysis": """
# Evaluate cash flow health:
# 1. Operating cash flow trends
# 2. Free cash flow calculation
# 3. Cash conversion cycle
# 4. Working capital changes
# 5. Burn rate and runway (for startups)
# """,
#     "trend_analysis": """
# Identify trends by analyzing:
# 1. Month-over-month changes
# 2. Quarter-over-quarter changes
# 3. Year-over-year growth
# 4. Seasonal patterns
# 5. Emerging patterns or anomalies
# """
# }

# # System prompt templates for different query types
# AI_SYSTEM_PROMPTS = {
#     "financial_expert": """You are working in a large conglomerate with multiple business units (BUs) and regions. 
#                         Each Finance Business Partner (BP) currently prepares monthly reports manually by 
#                         extracting data from different SAP instances, performing analysis in Excel, and 
#                         summarizing key points in PowerPoint for management.

# CRITICAL LANGUAGE RULE: Same to question language

# Your capabilities:
# - Deep understanding of financial statements (P&L, Balance Sheet, Cash Flow)
# - Expertise in financial ratios, KPIs, and performance metrics
# - Variance analysis and budget vs actual comparisons
# - Trend identification and forecasting
# - Clear explanation of complex financial concepts

# When analyzing data:
# 1. Start with high-level insights
# 2. Provide specific numbers and percentages
# 3. Identify trends and patterns
# 4. Highlight variances and anomalies
# 5. Offer actionable recommendations

# Always:
# - Respond in English only (regardless of question language)
# - Be precise with numbers and calculations
# - Explain financial terminology when used
# - Provide context for metrics (industry standards, historical performance)
# - Flag data quality issues or assumptions made
# - Maintain professional, concise communication

# Financial domain knowledge:
# {financial_glossary}

# Available formulas:
# {financial_formulas}
# """,

#     "executive_summary": """You are creating an executive summary for C-level management.

# Guidelines:
# - Lead with the most important insights
# - Use clear, non-technical language
# - Highlight key metrics that matter to executives
# - Include comparisons (vs budget, vs prior period)
# - Identify risks and opportunities
# - Keep summaries concise (3-5 key points)
# - Use bullet points for clarity

# Focus on:
# - Revenue and profitability trends
# - Cash flow health
# - Major variances from plan
# - Strategic implications
# - Recommended actions
# """,

#     "detailed_analysis": """You are conducting a detailed financial analysis for finance professionals.

# Approach:
# - Provide comprehensive numerical analysis
# - Show calculations and methodology
# - Include multiple perspectives (time series, cross-sectional)
# - Use financial ratios and metrics extensively
# - Identify correlations and drivers
# - Validate data quality and completeness

# Analysis should include:
# - Detailed variance analysis
# - Trend analysis (MoM, QoQ, YoY)
# - Ratio analysis
# - Benchmarking where applicable
# - Statistical insights
# - Data quality notes

# Answer in a structured:
# - Source of information: (uploaded data or database with table name)
# - Methodology: (steps taken for analysis)
# - Findings: (detailed results with numbers)
# """
# }

# def get_financial_context():
#     """Generate financial knowledge context for AI prompts"""
#     context = "FINANCIAL KNOWLEDGE BASE:\n\n"

#     context += "Key Terms:\n"
#     for term, definition in list(FINANCIAL_GLOSSARY.items())[:10]:
#         context += f"- {term.upper()}: {definition}\n"

#     context += "\nKey Formulas:\n"
#     for metric, details in list(FINANCIAL_FORMULAS.items())[:5]:
#         context += f"- {metric.upper()}: {details['formula']}\n"

#     return context

# def calculate_financial_metrics(data_df):
#     """Calculate common financial metrics from DataFrame"""
#     import pandas as pd

#     metrics = {}

#     # Revenue metrics
#     revenue = data_df[data_df['category'] == 'Revenue']['amount'].sum()
#     cogs = abs(data_df[data_df['category'] == 'COGS']['amount'].sum())
#     opex = abs(data_df[data_df['category'] == 'OpEx']['amount'].sum())

#     metrics['total_revenue'] = revenue
#     metrics['total_cogs'] = cogs
#     metrics['total_opex'] = opex
#     metrics['gross_profit'] = revenue - cogs
#     metrics['gross_margin'] = (metrics['gross_profit'] / revenue * 100) if revenue > 0 else 0
#     metrics['operating_income'] = revenue - cogs - opex
#     metrics['operating_margin'] = (metrics['operating_income'] / revenue * 100) if revenue > 0 else 0

#     # EBITDA (if depreciation/amortization present)
#     non_cash = abs(data_df[data_df['category'] == 'Non-Cash']['amount'].sum())
#     metrics['ebitda'] = metrics['operating_income'] + non_cash
#     metrics['ebitda_margin'] = (metrics['ebitda'] / revenue * 100) if revenue > 0 else 0

#     return metrics

# def explain_variance(actual, budget, threshold=0.1):
#     """Explain variance between actual and budget"""
#     variance = actual - budget
#     variance_pct = (variance / budget * 100) if budget != 0 else 0

#     if abs(variance_pct) < threshold * 100:
#         significance = "minimal"
#     elif abs(variance_pct) < 20:
#         significance = "moderate"
#     else:
#         significance = "significant"

#     direction = "favorable" if variance > 0 else "unfavorable"

#     return {
#         "variance_amount": variance,
#         "variance_percentage": variance_pct,
#         "significance": significance,
#         "direction": direction,
#         "explanation": f"{significance.capitalize()} {direction} variance of ${variance:,.0f} ({variance_pct:.1f}%)"
#     }
