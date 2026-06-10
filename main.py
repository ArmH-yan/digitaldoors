"""
Lead Generation Scraper — Main Pipeline
Simple synchronous pipeline for scraping Armenian construction companies.
"""

import time
from datetime import datetime
from src.database import get_engine, init_schema, upsert_company, insert_project, insert_contact
from src.crawler import run_crawler
from src.scoring import score_company, generate_intelligence, normalize_company
from src.export import export_all_companies, export_qualified_leads, generate_summary_report


def run_pipeline():
    start = time.time()
    print("=" * 60)
    print("  LEAD GENERATION PIPELINE")
    print(f"  Run time: {datetime.utcnow().isoformat()}")
    print("=" * 60)

    # Step 1: Init database
    print("\n[1/4] Initializing database schema...")
    engine = get_engine()
    init_schema()

    # Step 2: Crawl companies
    print("\n[2/4] Crawling construction.am...")
    companies = run_crawler()
    print(f"  Found {len(companies)} companies")

    # Step 3: Score and normalize
    print("\n[3/4] Scoring and normalizing leads...")
    for company in companies:
        normalize_company(company)
        score_company(company)
        intelligence = generate_intelligence(company)
        company["company_intelligence"] = intelligence

    companies.sort(key=lambda x: x.get("lead_score", 0), reverse=True)

    # Step 4: Store in database
    print("\n[4/4] Storing in database...")
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

    # Step 5: Export
    print("\n[EXPORT] Generating exports...")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    export_all_companies(companies, timestamp)
    export_qualified_leads(companies, timestamp)
    generate_summary_report(companies, timestamp)

    # Summary
    elapsed = round(time.time() - start, 2)
    hot = sum(1 for c in companies if c.get("lead_priority") == "HOT")
    warm = sum(1 for c in companies if c.get("lead_priority") == "WARM")

    print("\n" + "=" * 60)
    print(f"  PIPELINE COMPLETE in {elapsed}s")
    print(f"  Total companies:  {len(companies)}")
    print(f"  HOT leads:        {hot}")
    print(f"  WARM leads:       {warm}")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
