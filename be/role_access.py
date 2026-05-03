# # role_access.py
# # Role-based data access control for financial data

# """
# Simplified 2-Role System:
# 1. GCEO (Group CEO) - Strategic consolidated view across all BUs
# 2. BUGM (BU General Manager) - Detailed access to assigned BU only
# """

# ROLE_ACCESS_MATRIX = {
#     "gceo": {
#         "level": "STRATEGIC",
#         "description": "Group CEO - Consolidated strategic view across all business units",
#         "can_access": {
#             "financial_pl": "AGGREGATED",
#             "sap_gl_transactions": "AGGREGATED",
#             "balance_sheet": "AGGREGATED",
#             "cash_flow": "AGGREGATED",
#             "hfm_actuals": "CONSOLIDATED",
#             "hfm_budget": "CONSOLIDATED",
#             "variance_report": "SUMMARY"
#         },
#         "filters": {
#             # CEO sees aggregated by BU, category, period - no line-item details
#             "group_by": ["business_unit", "category", "period"]
#         },
#         "data_level": "Aggregated summaries by Business Unit, Category, and Period"
#     },

#     "bugm": {
#         "level": "BU_DETAILED",
#         "description": "BU General Manager - Full detailed access to assigned BU data only",
#         "can_access": {
#             "financial_pl": "BU_FILTERED",
#             "sap_gl_transactions": "BU_FILTERED",
#             "balance_sheet": "BU_FILTERED",
#             "cash_flow": "BU_FILTERED",
#             "hfm_actuals": "ENTITY_FILTERED",
#             "hfm_budget": "ENTITY_FILTERED",
#             "variance_report": "BU_FILTERED"
#         },
#         "filters": {
#             # Only see their assigned BU - detailed line-item access
#             "business_unit": ["ASSIGNED_BU"],
#             "entity": ["ASSIGNED_ENTITY"]
#         },
#         "data_level": "Full detailed line-item data for assigned Business Unit only"
#     }

# }


# def get_access_level(role: str, table: str) -> str:
#     """Get access level for a role on a specific table"""
#     if role not in ROLE_ACCESS_MATRIX:
#         return "NONE"

#     role_config = ROLE_ACCESS_MATRIX[role]
#     return role_config["can_access"].get(table, "NONE")


# def can_access_table(role: str, table: str) -> bool:
#     """Check if role can access a table"""
#     access = get_access_level(role, table)
#     return access != "NONE"


# def get_sql_filter(role: str, table: str, user_bu: str = None) -> str:
#     """
#     Generate SQL WHERE clause based on role and assigned BU

#     Args:
#         role: User role (gceo or bugm)
#         table: Table name
#         user_bu: User's assigned business unit (required for BUGM)

#     Returns:
#         SQL WHERE clause or empty string
#     """
#     access = get_access_level(role, table)

#     # Group CEO - no filter needed, will be aggregated
#     if role == "gceo":
#         return ""

#     # BU General Manager - filter by their assigned BU
#     if role == "bugm" and user_bu:
#         if table in ["financial_pl", "sap_gl_transactions", "balance_sheet", "cash_flow", "variance_report"]:
#             return f"WHERE business_unit = '{user_bu}'"

#         # HFM Entity filter for BU Manager
#         if table in ["hfm_actuals", "hfm_budget"]:
#             entity_map = {
#                 "APAC": "APAC_Singapore",
#                 "EMEA": "EMEA_Germany",
#                 "Americas": "AMERICAS_USA"
#             }
#             entity = entity_map.get(user_bu, user_bu)
#             return f"WHERE entity = '{entity}'"

#     # No access or invalid role
#     return "WHERE 1=0"


# def get_group_by_clause(role: str, table: str) -> str:
#     """Generate GROUP BY clause for aggregated views (GCEO only)"""
#     access = get_access_level(role, table)

#     # Group CEO gets aggregated data
#     if role == "gceo" and access in ["AGGREGATED", "CONSOLIDATED", "SUMMARY"]:
#         if table == "financial_pl":
#             return "GROUP BY business_unit, category, period ORDER BY period DESC, business_unit"
#         elif table == "sap_gl_transactions":
#             return "GROUP BY business_unit, account_name, period ORDER BY period DESC"
#         elif table == "balance_sheet":
#             return "GROUP BY business_unit, account_type, category ORDER BY business_unit"
#         elif table == "cash_flow":
#             return "GROUP BY business_unit, category, year, month ORDER BY year DESC, month DESC"
#         elif table in ["hfm_actuals", "hfm_budget"]:
#             return "GROUP BY entity, account, period ORDER BY period DESC"
#         elif table == "variance_report":
#             return "GROUP BY business_unit, period ORDER BY period DESC, business_unit"

#     # BU Manager gets detailed data - no GROUP BY
#     return ""


# def get_user_bu(email: str = None, token_payload: dict = None) -> str:
#     """Get user's assigned business unit from Auth0 token claims"""
#     if token_payload:
#         namespace = "https://vietdataverse.online"
#         return token_payload.get(f"{namespace}/business_unit", None)
#     return None


# def get_accessible_data_summary(role: str, user_email: str = None) -> str:
#     """Get summary of what data this role can access"""
#     if role not in ROLE_ACCESS_MATRIX:
#         return "Invalid role. Contact administrator."

#     role_config = ROLE_ACCESS_MATRIX[role]
#     user_bu = get_user_bu(user_email) if user_email else None

#     accessible = []
#     for table, access in role_config["can_access"].items():
#         if access != "NONE":
#             accessible.append(f"- {table}: {access}")

#     bu_info = ""
#     if role == "bugm" and user_bu:
#         bu_info = f"\nAssigned Business Unit: {user_bu} (can only see this BU's data)"
#     elif role == "gceo":
#         bu_info = "\nBusiness Unit Coverage: ALL (aggregated view)"

#     return f"""
# Role: {role.upper()}
# Access Level: {role_config['level']}
# Description: {role_config['description']}
# Data Level: {role_config['data_level']}
# {bu_info}

# Accessible Data Tables:
# {chr(10).join(accessible)}
# """


# def validate_role(role: str) -> bool:
#     """Validate if role is one of the allowed roles"""
#     return role in ["gceo", "bugm"]


# def get_role_description(role: str) -> str:
#     """Get human-readable description of role"""
#     descriptions = {
#         "gceo": "Group CEO - Strategic consolidated view of all business units",
#         "bugm": "BU General Manager - Detailed access to assigned business unit"
#     }
#     return descriptions.get(role, "Unknown role")
