"""
Lead Generation Scraper — Export
CSV and XLSX export for leads.
"""

import os
import csv
import pandas as pd
from datetime import datetime, timezone


EXPORT_DIR = "data/exports"


def ensure_export_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)


def export_all_companies(companies: list[dict], timestamp: str = None) -> str:
    ensure_export_dir()
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    filepath = os.path.join(EXPORT_DIR, f"companies_{timestamp}.csv")
    columns = [
        "company_name", "website", "phone", "email", "address", "city",
        "company_category", "company_description", "services",
        "contact_page_url", "source_url", "has_active_projects",
        "project_count", "project_names", "lead_score", "lead_priority"
    ]

    _write_csv(filepath, companies, columns)
    print(f"  [OK] Exported {len(companies)} companies to {filepath}")
    return filepath


def export_qualified_leads(companies: list[dict], timestamp: str = None) -> tuple[str, str]:
    ensure_export_dir()
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    qualified = [c for c in companies if c.get("lead_priority") in ("HOT", "WARM")]

    # CSV
    csv_path = os.path.join(EXPORT_DIR, f"qualified_leads_{timestamp}.csv")
    columns = [
        "company_name", "website", "phone", "email", "address", "city",
        "company_category", "services", "lead_score", "lead_priority",
        "project_count", "project_names", "company_intelligence"
    ]
    _write_csv(csv_path, qualified, columns)
    print(f"  [OK] Exported {len(qualified)} qualified leads to {csv_path}")

    # XLSX
    xlsx_path = os.path.join(EXPORT_DIR, f"qualified_leads_{timestamp}.xlsx")
    _write_xlsx(xlsx_path, qualified, columns)
    print(f"  [OK] Exported {len(qualified)} qualified leads to {xlsx_path}")

    return csv_path, xlsx_path


def generate_summary_report(companies: list[dict], timestamp: str = None) -> str:
    ensure_export_dir()
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    total = len(companies)
    if total == 0:
        print("  [WARN] No companies to report on")
        return ""

    report_path = os.path.join(EXPORT_DIR, f"summary_report_{timestamp}.txt")

    with_website = sum(1 for c in companies if c.get("website"))
    with_email = sum(1 for c in companies if c.get("email"))
    with_phone = sum(1 for c in companies if c.get("phone"))
    with_projects = sum(1 for c in companies if c.get("has_active_projects"))
    hot = sum(1 for c in companies if c.get("lead_priority") == "HOT")
    warm = sum(1 for c in companies if c.get("lead_priority") == "WARM")
    low = sum(1 for c in companies if c.get("lead_priority") == "COLD")
    avg_score = sum(c.get("lead_score", 0) for c in companies) / total

    report = f"""
====================================================
LEAD GENERATION SUMMARY REPORT
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
====================================================

OVERVIEW
--------
Total companies found:      {total}
Companies with website:     {with_website} ({with_website/total*100:.1f}%)
Companies with email:       {with_email} ({with_email/total*100:.1f}%)
Companies with phone:       {with_phone} ({with_phone/total*100:.1f}%)
Companies with projects:    {with_projects} ({with_projects/total*100:.1f}%)

LEAD DISTRIBUTION
-----------------
HOT leads:                  {hot} ({hot/total*100:.1f}%)
WARM leads:                 {warm} ({warm/total*100:.1f}%)
COLD leads:                  {low} ({low/total*100:.1f}%)

Average lead score:         {avg_score:.1f}

TOP 10 LEADS
-------------
"""

    sorted_companies = sorted(companies, key=lambda x: x.get("lead_score", 0), reverse=True)
    for i, c in enumerate(sorted_companies[:10], 1):
        report += f"{i}. {c.get('company_name', 'N/A')} - Score: {c.get('lead_score', 0)} ({c.get('lead_priority', 'N/A')})\n"

    report += "\n====================================================\n"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"  [OK] Summary report: {report_path}")
    return report_path


def _write_csv(filepath: str, data: list[dict], columns: list[str]):
    if not data:
        return
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def _write_xlsx(filepath: str, data: list[dict], columns: list[str]):
    if not data:
        return
    df = pd.DataFrame(data)
    available = [c for c in columns if c in df.columns]
    df = df[available]

    rename = {
        "company_name": "Company Name", "website": "Website", "phone": "Phone",
        "email": "Email", "address": "Address", "city": "City",
        "company_category": "Category", "services": "Services",
        "lead_score": "Score", "lead_priority": "Priority",
        "project_count": "Projects", "project_names": "Project Names",
        "company_intelligence": "Intelligence",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")
