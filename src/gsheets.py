"""
Lead Generation v2 — Google Sheets Sync
Sync unsynced companies to Google Sheets warehouse.
Each source gets its own worksheet tab.
"""

import os
import logging
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

log = logging.getLogger("leadgen")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials/gsheets_key.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Source key -> worksheet tab name
SOURCE_WORKSHEETS = {
    "construction.am": "Construction Leads",
    "spyur.am": "Spyur Leads",
    "defansehousing": "Defanse Leads",
    "norakaruyc.am": "Norakaruyc Leads",
}

DEFAULT_WORKSHEET = "Leads"

HEADERS = [
    "company_name", "website", "phone", "email", "address", "city",
    "district", "director", "founded_year", "employee_count", "ownership_type",
    "gps_lat", "gps_lon",
    "facebook_url", "instagram_url", "linkedin_url",
    "services", "lead_score", "lead_priority",
    "project_count", "has_active_projects", "project_names", "company_intelligence",
    "company_category", "source_site", "source_url", "first_seen", "last_seen"
]

DISPLAY_HEADERS = [
    "Company Name", "Website", "Phone", "Email", "Address", "City",
    "District", "Director", "Founded Year", "Employees", "Ownership",
    "Latitude", "Longitude",
    "Facebook", "Instagram", "LinkedIn",
    "Services", "Score", "Priority",
    "Project Count", "Has Active Projects", "Project Names", "Intelligence",
    "Ecosystem Category", "Source", "Source URL", "First Seen", "Last Seen"
]


def get_gspread_client():
    """Authenticate and return gspread client."""
    if not os.path.exists(CREDS_FILE):
        log.warning(f"  Google credentials not found: {CREDS_FILE}")
        log.warning(f"  Skipping Google Sheets sync")
        return None

    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_worksheet_name(source_site: str) -> str:
    """Map source_site to worksheet tab name."""
    return SOURCE_WORKSHEETS.get(source_site, DEFAULT_WORKSHEET)


def sync_to_sheets(companies: list[dict], worksheet_name: str = None) -> int:
    """Sync companies to Google Sheets. Updates existing rows, appends new ones."""
    if not SPREADSHEET_ID:
        log.warning("  GOOGLE_SHEET_ID not set. Skipping sync.")
        return 0

    client = get_gspread_client()
    if not client:
        return 0

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        log.error(f"  Cannot open spreadsheet: {e}")
        return 0

    # Determine worksheet name from first company's source if not provided
    if not worksheet_name and companies:
        worksheet_name = _get_worksheet_name(companies[0].get("source_site", ""))
    if not worksheet_name:
        worksheet_name = DEFAULT_WORKSHEET

    # Get or create worksheet
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(HEADERS) + 1)
        log.info(f"  Created worksheet: {worksheet_name}")

    # Make sure display headers are set as first row
    ensure_headers(worksheet)

    # Read existing data and build dedup map: key -> row_index (1-based, excluding header)
    existing_map = {}  # key -> row_number
    try:
        all_values = worksheet.get_all_values()
        if len(all_values) > 1:
            header_row = all_values[0]
            name_idx = header_row.index("Company Name") if "Company Name" in header_row else 0
            phone_idx = header_row.index("Phone") if "Phone" in header_row else 2
            addr_idx = header_row.index("Address") if "Address" in header_row else 4
            for i, row in enumerate(all_values[1:], start=2):
                key = _dedup_key(row[name_idx], row[phone_idx], row[addr_idx])
                if key:
                    existing_map[key] = i  # row number in the sheet (1-based, row 1 = header)
            log.info(f"  [{worksheet_name}] Found {len(existing_map)} existing rows")
    except Exception as e:
        log.warning(f"  Could not read existing sheet data: {e}")

    # Separate into updates and appends
    updates = []  # (row_number, row_data)
    appends = []  # row_data
    updated = 0
    appended = 0

    for company in companies:
        row = _company_to_row(company)
        name = company.get("company_name", "")
        phone = company.get("phone", "")
        addr = company.get("address", "")
        key = _dedup_key(name, phone, addr)

        if key and key in existing_map:
            updates.append((existing_map[key], row))
        else:
            appends.append(row)
            if key:
                # Track so duplicates within same batch go to append too
                new_row_num = len(existing_map) + len(appends) + 1
                existing_map[key] = new_row_num

    # Batch update existing rows
    if updates:
        try:
            cell_list = []
            for row_num, row_data in updates:
                for col_idx, val in enumerate(row_data):
                    cell_list.append(gspread.Cell(row=row_num, col=col_idx + 1, value=val))
            worksheet.update_cells(cell_list)
            updated = len(updates)
            log.info(f"  [{worksheet_name}] Updated {updated} existing rows")
        except Exception as e:
            log.error(f"  [{worksheet_name}] Batch update failed: {e}")

    # Append new rows
    if appends:
        try:
            worksheet.append_rows(appends, value_input_option="USER_ENTERED")
            appended = len(appends)
            log.info(f"  [{worksheet_name}] Appended {appended} new rows")
        except Exception as e:
            log.error(f"  [{worksheet_name}] Append failed: {e}")

    total = updated + appended
    if total == 0:
        log.info(f"  [{worksheet_name}] No changes to sync")
    else:
        log.info(f"  [{worksheet_name}] Sync complete: {updated} updated, {appended} new")
    return total


def _company_to_row(company: dict) -> list[str]:
    """Convert a company dict to a row list matching HEADERS order."""
    row = []
    for h in HEADERS:
        val = company.get(h, "")
        if h == "has_active_projects":
            val = "TRUE" if val else "FALSE"
        elif h == "lead_score":
            val = str(val) if val else "0"
        else:
            if val is None or (isinstance(val, float) and val != val):  # NaN check
                val = ""
            else:
                val = str(val)
        row.append(val)
    return row


def _dedup_key(name: str, phone: str, address: str) -> str:
    """Build a normalized dedup key from company name, phone, and address."""
    name = str(name).strip().lower() if name else ""
    phone = str(phone).strip() if phone else ""
    address = str(address).strip().lower() if address else ""
    if not name and not phone:
        return ""
    return "|".join([name, phone, address])


def ensure_headers(worksheet):
    """Write display-friendly headers as the first row."""
    existing = worksheet.row_values(1)
    if not existing or existing != DISPLAY_HEADERS:
        worksheet.update(range_name="A1", values=[DISPLAY_HEADERS])
