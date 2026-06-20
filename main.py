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

from src.crawler import run_crawler, SOURCES
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

PAGE_LIMITS = {
    "construction_am": 38,
    "spyur_am": 20,
}


def get_user_config(sources: list[str]) -> dict:
    """Prompt user for max pages per source. Returns dict of source -> max_pages."""
    config = {}
    for source in sources:
        max_allowed = PAGE_LIMITS.get(source)
        if max_allowed is None:
            continue
        try:
            ans = input(
                f"  Max pages for {source}? (1-{max_allowed}, Enter=all): "
            ).strip()
            if ans:
                val = int(ans)
                if 1 <= val <= max_allowed:
                    config[source] = val
                else:
                    print(f"    Invalid, using all {max_allowed} pages")
            else:
                print(f"    Using all {max_allowed} pages")
        except (ValueError, EOFError):
            print(f"    Using all {max_allowed} pages")
    return config


def _store_company(engine, company: dict):
    """Store a single company and its contacts in the database."""
    company_id = upsert_company(engine, company)

    project_names = company.get("project_names", "")
    if project_names:
        for name in project_names.split(", "):
            if name.strip():
                insert_project(
                    engine,
                    company_id,
                    name.strip(),
                    source=company.get("source_url"),
                )

    if company.get("phone"):
        insert_contact(
            engine,
            company_id,
            "phone",
            company["phone"],
            company.get("source_url"),
        )

    if company.get("email"):
        insert_contact(
            engine,
            company_id,
            "email",
            company["email"],
            company.get("source_url"),
        )

    return company_id


def _sync_batch(engine, log):
    """Sync all unsynced companies from DB to Google Sheets."""
    unsynced = get_unsynced_companies(engine)
    if unsynced.empty:
        return 0
    unsynced_list = unsynced.to_dict("records")
    synced_count = sync_to_sheets(unsynced_list)
    if synced_count > 0:
        ids = unsynced["id"].tolist()
        mark_synced(engine, ids)
        log.info(f"    Synced {len(ids)} companies to Google Sheets")
    return synced_count


def run_pipeline(sources: list[str] = None, config: dict = None):
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

    # Graceful shutdown handling
    interrupted = False

    def handle_interrupt(sig, frame):
        nonlocal interrupted
        if interrupted:
            log.warning("  Force exit.")
            sys.exit(1)
        log.warning("  Interrupt received — finishing current batch...")
        interrupted = True

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    # Step 1: Init database
    log.info("[1/4] Initializing database schema...")
    engine = get_engine()
    init_schema()

    # Step 2: Crawl + score + store per source (incremental)
    log.info("[2/4] Crawling web sources...")
    if sources is None:
        sources = list(SOURCES.keys())

    max_pages_per_source = config or {}

    all_companies = []

    # Process each source individually for incremental save
    from src.crawler import run_source, create_agents, BatchBuffer

    agents = create_agents(5)

    # Handle defanse_housing separately (targeted scraper)
    if "defanse_housing" in sources:
        from src.scrapers.defanse_housing import DefanseHousingScraper
        if interrupted:
            log.warning("  Stopped before defanse_housing")
        else:
            log.info("  Source: defanse_housing (targeted)")
            dh = DefanseHousingScraper()
            dh_companies = dh.run()

            # Score, store, sync
            for c in dh_companies:
                normalize_company(c)
                score_company(c)
                c["company_intelligence"] = generate_intelligence(c)
                _store_company(engine, c)
            _sync_batch(engine, log)

            all_companies.extend(dh_companies)
            log.info(f"    defanse_housing: {len(dh_companies)} companies saved")
        sources = [s for s in sources if s != "defanse_housing"]

    # Process directory sources
    for source_key in sources:
        if interrupted:
            log.warning(f"  Stopped before {source_key}")
            break
        if source_key not in SOURCES:
            log.warning(f"  Unknown source: {source_key}")
            continue

        max_pages = max_pages_per_source.get(source_key)

        def on_batch_flush(batch):
            """Callback: score + store + sync every 100 profiles."""
            for c in batch:
                normalize_company(c)
                score_company(c)
                c["company_intelligence"] = generate_intelligence(c)
                _store_company(engine, c)
            _sync_batch(engine, log)

        buffer = BatchBuffer(on_flush=on_batch_flush)
        companies = run_source(source_key, SOURCES[source_key], agents, buffer, max_pages=max_pages)

        # Score remaining items in buffer
        remaining = buffer.buffer[:]
        buffer.buffer.clear()
        for c in remaining:
            normalize_company(c)
            score_company(c)
            c["company_intelligence"] = generate_intelligence(c)
            _store_company(engine, c)

        # Final sync for this source
        _sync_batch(engine, log)

        all_companies.extend(companies)
        all_companies.extend(remaining)
        log.info(f"  {source_key}: {len(companies) + len(remaining)} companies saved")

    # Export local files
    log.info("[EXPORT] Generating exports...")
    export_all_companies(all_companies, run_id)
    export_qualified_leads(all_companies, run_id)
    generate_summary_report(all_companies, run_id)

    # Summary
    elapsed = round(time.time() - start, 2)
    hot = sum(1 for c in all_companies if c.get("lead_priority") == "HOT")
    warm = sum(1 for c in all_companies if c.get("lead_priority") == "WARM")

    log.info("=" * 60)
    log.info(f"  PIPELINE COMPLETE in {elapsed}s")
    log.info(f"  Run ID:          {run_id}")
    log.info(f"  Total companies: {len(all_companies)}")
    log.info(f"  HOT leads:       {hot}")
    log.info(f"  WARM leads:      {warm}")
    if interrupted:
        log.info(f"  (Interrupted — partial results saved)")
    log.info("=" * 60)

    return all_companies


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

    # Prompt for page limits
    config = None
    if sources:
        config = get_user_config(sources)
    else:
        config = get_user_config(list(SOURCES.keys()))

    run_pipeline(sources=sources, config=config)


if __name__ == "__main__":
    main()
