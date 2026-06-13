"""
Lead Generation v2 — Main Pipeline
Scrape → Score → Store → Sync to Sheets → Purge temp
"""

import sys
import io
import os
import time
import signal
from pathlib import Path
from datetime import datetime, timezone

# UTF-8 stdout support
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Load environment variables
try:
    from dotenv import load_dotenv
except ImportError:
    raise ImportError(
        "python-dotenv is not installed. Install it with: pip install python-dotenv"
    )

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

# Config
RUN_INTERVAL_HOURS = int(os.getenv("RUN_INTERVAL_HOURS", "6"))

# Validate important env vars
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")

from src.log import setup_logging, get_logger

from src.database import (
    get_engine,
    init_schema,
    upsert_company,
    insert_project,
    insert_contact,
    get_unsynced_companies,
    mark_synced,
    purge_synced,
    get_summary,
)

from src.crawler import run_crawler
from src.scoring import (
    score_company,
    generate_intelligence,
    normalize_company,
)

from src.gsheets import sync_to_sheets
from src.export import (
    export_all_companies,
    export_qualified_leads,
    generate_summary_report,
)


def run_pipeline(sources: list[str] = None):
    start = time.time()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    log = setup_logging(run_id)

    log.info("=" * 60)
    log.info("  LEAD GENERATION PIPELINE v2")
    log.info(f"  Run ID:   {run_id}")
    log.info(f"  Started:  {datetime.now(timezone.utc).isoformat()}")
    log.info("=" * 60)

    if not GOOGLE_SHEET_ID:
        log.warning("GOOGLE_SHEET_ID not found in .env")
    if not GOOGLE_CREDS_FILE:
        log.warning("GOOGLE_CREDS_FILE not found in .env")
    if not GOOGLE_SHEET_NAME:
        log.warning("GOOGLE_SHEET_NAME not found in .env")

    # Step 1: Init database
    log.info("[1/5] Initializing database schema...")
    engine = get_engine()
    init_schema()

    # Step 2: Crawl companies
    log.info("[2/5] Crawling web sources...")
    companies, buffer = run_crawler(num_agents=5, sources=sources)
    log.info(f"  Found {len(companies)} companies")

    # Step 3: Score and normalize
    log.info("[3/5] Scoring and normalizing leads...")
    for company in companies:
        normalize_company(company)
        score_company(company)
        company["company_intelligence"] = generate_intelligence(company)
        company["run_id"] = run_id

    companies.sort(
        key=lambda x: x.get("lead_score", 0),
        reverse=True
    )

    # Step 4: Store in database
    log.info("[4/5] Storing in database (temp)...")
    for company in companies:
        company_id = upsert_company(engine, company)

        project_names = company.get("project_names", "")
        if project_names:
            for name in project_names.split(", "):
                if name.strip():
                    insert_project(
                        engine,
                        company_id,
                        name.strip(),
                        source=company.get("source_url")
                    )

        if company.get("phone"):
            insert_contact(
                engine,
                company_id,
                "phone",
                company["phone"],
                company.get("source_url")
            )

        if company.get("email"):
            insert_contact(
                engine,
                company_id,
                "email",
                company["email"],
                company.get("source_url")
            )

    log.info(f"  Stored {len(companies)} companies in database")

    # Step 5: Sync to Google Sheets
    log.info("[5/5] Syncing to Google Sheets...")
    unsynced = get_unsynced_companies(engine)

    if not unsynced.empty:
        unsynced_list = unsynced.to_dict("records")
        synced_count = sync_to_sheets(unsynced_list)

        if synced_count > 0:
            ids = unsynced["id"].tolist()
            mark_synced(engine, ids)
            log.info(f"  Marked {len(ids)} companies as synced")
    else:
        log.info("  No unsynced companies")

    # Export local files
    log.info("[EXPORT] Generating exports...")
    export_all_companies(companies, run_id)
    export_qualified_leads(companies, run_id)
    generate_summary_report(companies, run_id)

    # Optional purge synced data
    # purge_synced(engine)

    # Summary
    elapsed = round(time.time() - start, 2)
    hot = sum(
        1 for c in companies
        if c.get("lead_priority") == "HOT"
    )
    warm = sum(
        1 for c in companies
        if c.get("lead_priority") == "WARM"
    )

    log.info("=" * 60)
    log.info(f"  PIPELINE COMPLETE in {elapsed}s")
    log.info(f"  Run ID:          {run_id}")
    log.info(f"  Total companies: {len(companies)}")
    log.info(f"  HOT leads:       {hot}")
    log.info(f"  WARM leads:      {warm}")
    log.info("=" * 60)

    return companies


def run_scheduled():
    log = get_logger()
    log.info(f"Scheduler started. Running every {RUN_INTERVAL_HOURS} hours.")
    log.info("Press Ctrl+C to stop.")

    running = True

    def handle_signal(sig, frame):
        nonlocal running
        log.info("Stopping scheduler...")
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while running:
        try:
            run_pipeline()
        except Exception as e:
            log.error(f"Pipeline failed: {e}", exc_info=True)

        if not running:
            break

        log.info(f"Next run in {RUN_INTERVAL_HOURS} hours...")

        for _ in range(RUN_INTERVAL_HOURS * 3600):
            if not running:
                break
            time.sleep(1)


def main():
    sources = None

    if len(sys.argv) > 1:
        if sys.argv[1] == "--schedule":
            run_scheduled()
            return

        sources = sys.argv[1:]

    run_pipeline(sources=sources)


if __name__ == "__main__":
    main()
