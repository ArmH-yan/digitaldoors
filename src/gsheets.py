"""
Lead Generation v2 — Google Sheets Sync
Sync unsynced companies to Google Sheets warehouse.
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials/gsheets_key.json")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Leads")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "company_name", "website", "phone", "email", "address", "city",
    "company_category", "services", "lead_score", "lead_priority",
    "project_count", "project_names", "company_intelligence",
    "source_site", "source_url", "first_seen", "last_seen"
]


def get_gspread_client():
    """Authenticate and return gspread client."""
    if not os.path.exists(CREDS_FILE):
        print(f"  [WARN] Google credentials not found: {CREDS_FILE}")
        print(f"  [WARN] Skipping Google Sheets sync")
        return None

    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def sync_to_sheets(companies: list[dict]) -> int:
    """Sync companies to Google Sheets. Returns count synced."""
    if not SPREADSHEET_ID:
        print("  [WARN] GOOGLE_SHEET_ID not set. Skipping sync.")
        return 0

    client = get_gspread_client()
    if not client:
        return 0

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        print(f"  [ERROR] Cannot open spreadsheet: {e}")
        return 0

    # Get or create worksheet
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS) + 1)

    # Prepare rows
    rows = []
    for company in companies:
        row = [str(company.get(h, "")) for h in HEADERS]
        rows.append(row)

    if not rows:
        print("  [INFO] No rows to sync")
        return 0

    # Append rows
    try:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"  [OK] Synced {len(rows)} rows to Google Sheets")
        return len(rows)
    except Exception as e:
        print(f"  [ERROR] Sync failed: {e}")
        return 0


def ensure_headers(worksheet):
    """Make sure headers are set."""
    existing = worksheet.row_values(1)
    if not existing or existing != HEADERS:
        worksheet.update(range_name="A1", values=[HEADERS])
