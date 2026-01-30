# import os
# import json
# from pathlib import Path
# from typing import Optional, Dict, Any
# import logging

# logger = logging.getLogger(__name__)

# # Optional imports - gracefully handle if not installed
# try:
#     import pandas as pd
#     PANDAS_AVAILABLE = True
# except ImportError:
#     PANDAS_AVAILABLE = False
#     logger.warning("pandas not installed - Excel/CSV processing disabled")

# try:
#     import PyPDF2
#     PDF_AVAILABLE = True
# except ImportError:
#     PDF_AVAILABLE = False
#     logger.warning("PyPDF2 not installed - PDF processing disabled")

# try:
#     import openpyxl
#     OPENPYXL_AVAILABLE = True
# except ImportError:
#     OPENPYXL_AVAILABLE = False
#     logger.warning("openpyxl not installed - Excel write support limited")


# ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.pdf'}
# MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
#     """Validate uploaded file"""
#     # Check extension
#     file_ext = Path(filename).suffix.lower()
#     if file_ext not in ALLOWED_EXTENSIONS:
#         return False, f"File type {file_ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

#     # Check size
#     if file_size > MAX_FILE_SIZE:
#         return False, f"File size {file_size} exceeds maximum {MAX_FILE_SIZE} bytes"

#     # Check specific library availability
#     if file_ext == '.pdf' and not PDF_AVAILABLE:
#         return False, "PDF processing not available - PyPDF2 not installed"

#     if file_ext in ['.csv', '.xlsx', '.xls'] and not PANDAS_AVAILABLE:
#         return False, "Excel/CSV processing not available - pandas not installed"

#     return True, "OK"


# def read_csv_file(file_path: str) -> Dict[str, Any]:
#     """Read CSV file and save as JSON for fast access"""
#     if not PANDAS_AVAILABLE:
#         return {"error": "pandas not installed"}

#     try:
#         df = pd.read_csv(file_path)

#         # Clean data
#         df = df.replace({'-': ''}, regex=True)

#         # Convert numeric columns
#         for col in df.columns:
#             df[col] = pd.to_numeric(df[col], errors='ignore')

#         # Save full data to JSON for fast access
#         json_path = file_path.replace('.csv', '.json')
#         df.to_json(json_path, orient='records', indent=2)

#         # Generate summary for LLM
#         summary = {
#             "file_type": "CSV",
#             "rows": len(df),
#             "columns": len(df.columns),
#             "column_names": df.columns.tolist(),
#             "preview": df.head(5).to_dict('records'),  # Only 5 rows
#             "data_types": df.dtypes.astype(str).to_dict(),
#             "statistics": {}
#         }

#         # Add aggregated statistics for numeric columns
#         numeric_cols = df.select_dtypes(include=['number']).columns
#         if len(numeric_cols) > 0:
#             # Only mean, sum, min, max (no percentiles)
#             stats = df[numeric_cols].agg(['mean', 'sum', 'min', 'max']).to_dict()
#             summary["statistics"] = stats

#         # Store JSON path for fast reading
#         summary["json_file_path"] = json_path
#         summary["original_file_path"] = file_path
#         summary["preview_string"] = df.head(5).to_string()  # Only 5 rows preview

#         return summary

#     except Exception as e:
#         logger.error(f"Error reading CSV file: {e}")
#         return {"error": f"Failed to read CSV: {str(e)}"}


# def read_excel_file(file_path: str) -> Dict[str, Any]:
#     """Read Excel file and save as JSON for fast access"""
#     if not PANDAS_AVAILABLE:
#         return {"error": "pandas not installed"}

#     try:
#         # Read Excel file (supports both .xlsx and .xls)
#         excel_file = pd.ExcelFile(file_path)

#         summary = {
#             "file_type": "Excel",
#             "sheet_names": excel_file.sheet_names,
#             "sheets": {}
#         }

#         # Read all sheets and save to JSON
#         for sheet_name in excel_file.sheet_names:
#             df = pd.read_excel(file_path, sheet_name=sheet_name)

#             # Clean data
#             df = df.replace({'-': ''}, regex=True)

#             # Convert numeric columns
#             for col in df.columns:
#                 df[col] = pd.to_numeric(df[col], errors='ignore')

#             # Save sheet data to JSON for fast access
#             json_path = file_path.replace('.xlsx', f'_{sheet_name}.json').replace('.xls', f'_{sheet_name}.json')
#             df.to_json(json_path, orient='records', indent=2)

#             sheet_summary = {
#                 "rows": len(df),
#                 "columns": len(df.columns),
#                 "column_names": df.columns.tolist(),
#                 "preview": df.head(5).to_dict('records'),  # Only 5 rows
#                 "data_types": df.dtypes.astype(str).to_dict()
#             }

#             # Add aggregated statistics for numeric columns
#             numeric_cols = df.select_dtypes(include=['number']).columns
#             if len(numeric_cols) > 0:
#                 stats = df[numeric_cols].agg(['mean', 'sum', 'min', 'max']).to_dict()
#                 sheet_summary["statistics"] = stats

#             # Store JSON path for fast reading
#             sheet_summary["json_file_path"] = json_path
#             sheet_summary["original_file_path"] = file_path
#             sheet_summary["sheet_name"] = sheet_name
#             sheet_summary["preview_string"] = df.head(5).to_string()

#             summary["sheets"][sheet_name] = sheet_summary

#         return summary

#     except Exception as e:
#         logger.error(f"Error reading Excel file: {e}")
#         return {"error": f"Failed to read Excel: {str(e)}"}


# def read_pdf_file(file_path: str) -> Dict[str, Any]:
#     """Read PDF file and extract text for LLM"""
#     if not PDF_AVAILABLE:
#         return {"error": "PyPDF2 not installed"}

#     try:
#         with open(file_path, 'rb') as file:
#             pdf_reader = PyPDF2.PdfReader(file)

#             num_pages = len(pdf_reader.pages)
#             text_content = []

#             # Extract text from all pages
#             for page_num in range(num_pages):
#                 page = pdf_reader.pages[page_num]
#                 text = page.extract_text()
#                 text_content.append({
#                     "page": page_num + 1,
#                     "text": text
#                 })

#             # Combine all text
#             full_text = "\n\n".join([f"Page {item['page']}:\n{item['text']}" for item in text_content])

#             summary = {
#                 "file_type": "PDF",
#                 "pages": num_pages,
#                 "text_by_page": text_content,
#                 "full_text": full_text,
#                 "preview": full_text[:2000] + "..." if len(full_text) > 2000 else full_text
#             }

#             return summary

#     except Exception as e:
#         logger.error(f"Error reading PDF file: {e}")
#         return {"error": f"Failed to read PDF: {str(e)}"}


# def process_uploaded_file(file_path: str, filename: str) -> Dict[str, Any]:
#     """Process uploaded file based on type and return summary for LLM"""

#     file_ext = Path(filename).suffix.lower()

#     if file_ext == '.csv':
#         return read_csv_file(file_path)
#     elif file_ext in ['.xlsx', '.xls']:
#         return read_excel_file(file_path)
#     elif file_ext == '.pdf':
#         return read_pdf_file(file_path)
#     else:
#         return {"error": f"Unsupported file type: {file_ext}"}


# def format_file_summary_for_llm(file_summary: Dict[str, Any], filename: str) -> str:
#     """Format file summary into COMPACT string for LLM context (OPTIMIZED)"""

#     if "error" in file_summary:
#         return f"Error: {file_summary['error']}"

#     file_type = file_summary.get("file_type", "Unknown")

#     if file_type == "CSV":
#         # COMPACT format - only essential info
#         stats_str = ""
#         if file_summary.get('statistics'):
#             stats = file_summary['statistics']
#             # Show only sum for key columns
#             stats_str = "\nKey Stats: " + ", ".join([f"{col}: sum={stats[col].get('sum', 'N/A')}" for col in list(stats.keys())[:3]])

#         context = f"""File: {filename} (CSV)
# {file_summary['rows']} rows × {file_summary['columns']} cols
# Columns: {', '.join(file_summary['column_names'][:5])}{"..." if len(file_summary['column_names']) > 5 else ""}
# {stats_str}
# Preview: {file_summary.get('preview_string', 'N/A')[:200]}...
# """
#         return context

#     elif file_type == "Excel":
#         # COMPACT format for Excel
#         sheets_info = []
#         for sheet_name, sheet_data in file_summary['sheets'].items():
#             sheets_info.append(f"{sheet_name}: {sheet_data['rows']}×{sheet_data['columns']}")

#         first_sheet = list(file_summary['sheets'].values())[0]
#         context = f"""File: {filename} (Excel)
# Sheets: {', '.join(sheets_info[:2])}{"..." if len(sheets_info) > 2 else ""}
# Preview: {first_sheet.get('preview_string', 'N/A')[:200]}...
# """
#         return context

#     elif file_type == "PDF":
#         context = f"""File: {filename} (PDF)
# {file_summary['pages']} pages
# Preview: {file_summary['preview'][:300]}...
# """
#         return context

#     return f"File: {filename}"


# def get_file_data_for_analysis(file_summary: Dict[str, Any]) -> Optional[Any]:
#     """Load actual data from JSON file (fast access)"""

#     if "error" in file_summary:
#         return None

#     file_type = file_summary.get("file_type")

#     if file_type == "CSV":
#         # Read from JSON file (fast)
#         json_path = file_summary.get("json_file_path")
#         if json_path and os.path.exists(json_path):
#             try:
#                 with open(json_path, 'r') as f:
#                     return json.load(f)
#             except Exception as e:
#                 logger.error(f"Error loading JSON file: {e}")
#                 return None
#         return None

#     elif file_type == "Excel":
#         # Read from JSON files (fast)
#         all_data = {}
#         for sheet_name, sheet_data in file_summary.get("sheets", {}).items():
#             json_path = sheet_data.get("json_file_path")
#             if json_path and os.path.exists(json_path):
#                 try:
#                     with open(json_path, 'r') as f:
#                         all_data[sheet_name] = json.load(f)
#                 except Exception as e:
#                     logger.error(f"Error loading JSON file: {e}")
#         return all_data if all_data else None

#     elif file_type == "PDF":
#         # PDF already has full_text in summary
#         return file_summary.get("full_text")

#     return None
