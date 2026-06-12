"""
Lead Generation v2 — Main Pipeline
Scrape → Score → Store → Sync to Sheets → Purge temp
"""

import sys
import io
import time
import signal
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from src.database import (
    get_engine, init_schema, upsert_company, insert_project, insert_contact,
    get_unsynced_companies, mark_synced, purge_synced, get_summary
)
from src.crawler import run_crawler
from src.scoring import score_company, generate_intelligence, normalize_company
from src.gsheets import sync_to_sheets
from src.export import export_all_companies, export_qualified_leads, generate_summary_report

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os

RUN_INTERVAL_HOURS = int(os.getenv("RUN_INTERVAL_HOURS", "6"))


def run_pipeline(sources: list[str] = None):
    start = time.time()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print("=" * 60)
    print("  LEAD GENERATION PIPELINE v2")
    print(f"  Run ID:   {run_id}")
    print(f"  Started:  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Step 1: Init database
    print("\n[1/5] Initializing database schema...")
    engine = get_engine()
    init_schema()

    # Step 2: Crawl companies
    print("\n[2/5] Crawling web sources...")
    companies, buffer = run_crawler(num_agents=5, sources=sources)
    print(f"  Found {len(companies)} companies")

    # Step 3: Score and normalize
    print("\n[3/5] Scoring and normalizing leads...")
    for company in companies:
        normalize_company(company)
        score_company(company)
        company["company_intelligence"] = generate_intelligence(company)
        company["run_id"] = run_id

    companies.sort(key=lambda x: x.get("lead_score", 0), reverse=True)

    # Step 4: Store in database (temp)
    print("\n[4/5] Storing in database (temp)...")
    for company in companies:
        company_id = upsert_company(engine, company)

        project_names = company.get("project_names", "")
        if project_names:
            for name in project_names.split(", "):
                if name.strip():
                    insert_project(engine, company_id, name.strip(), source=company.get("source_url"))

        if company.get("phone"):
            insert_contact(engine, company_id, "phone", company["phone"], company.get("source_url"))
        if company.get("email"):
            insert_contact(engine, company_id, "email", company["email"], company.get("source_url"))

    print(f"  Stored {len(companies)} companies in database")

    # Step 5: Sync to Google Sheets
    print("\n[5/5] Syncing to Google Sheets...")
    unsynced = get_unsynced_companies(engine)
    if not unsynced.empty:
        unsynced_list = unsynced.to_dict("records")
        synced_count = sync_to_sheets(unsynced_list)

        if synced_count > 0:
            ids = unsynced["id"].tolist()
            mark_synced(engine, ids)
            print(f"  Marked {len(ids)} companies as synced")
    else:
        print("  No unsynced companies")

    # Export local files
    print("\n[EXPORT] Generating exports...")
    all_companies_df = get_unsynced_companies(engine)  # temp table has all current data
    all_companies_list = all_companies_df.to_dict("records") if not all_companies_df.empty else companies

    export_all_companies(companies, run_id)
    export_qualified_leads(companies, run_id)
    generate_summary_report(companies, run_id)

    # Summary
    elapsed = round(time.time() - start, 2)
    hot = sum(1 for c in companies if c.get("lead_priority") == "HOT")
    warm = sum(1 for c in companies if c.get("lead_priority") == "WARM")

    print("\n" + "=" * 60)
    print(f"  PIPELINE COMPLETE in {elapsed}s")
    print(f"  Run ID:          {run_id}")
    print(f"  Total companies: {len(companies)}")
    print(f"  HOT leads:       {hot}")
    print(f"  WARM leads:      {warm}")
    print("=" * 60)

    return companies


def run_scheduled():
    print(f"Scheduler started. Running every {RUN_INTERVAL_HOURS} hours.")
    print("Press Ctrl+C to stop.\n")

    running = True

    def handle_signal(sig, frame):
        nonlocal running
        print("\nStopping scheduler...")
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while running:
        try:
            run_pipeline()
        except Exception as e:
            print(f"\n[ERROR] Pipeline failed: {e}")

        if not running:
            break

        print(f"\nNext run in {RUN_INTERVAL_HOURS} hours...")
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
