"""
Lead Generation Scraper — Database Module
Simple synchronous PostgreSQL with SQLAlchemy + psycopg2.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "leadgen")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")

SQL_DIR = "sql/schema"


def get_engine():
    url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, echo=False, pool_pre_ping=True)


def run_sql_file(engine, filepath: str):
    with open(filepath, encoding="utf-8") as f:
        sql = f.read()
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print(f"  [OK] Executed {filepath}")


def init_schema():
    engine = get_engine()
    run_sql_file(engine, f"{SQL_DIR}/01_schema.sql")
    print("  [OK] Schema initialized")


def upsert_company(engine, data: dict) -> int:
    """Insert or update company. Returns company ID."""
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM companies WHERE company_name = :name AND source_url = :source"),
            {"name": data["company_name"], "source": data.get("source_url", "")}
        ).fetchone()

        if existing:
            company_id = existing[0]
            conn.execute(text("""
                UPDATE companies SET
                    website = COALESCE(:website, website),
                    phone = COALESCE(:phone, phone),
                    email = COALESCE(:email, email),
                    address = COALESCE(:address, address),
                    city = COALESCE(:city, city),
                    company_category = COALESCE(:category, company_category),
                    company_description = COALESCE(:description, company_description),
                    services = COALESCE(:services, services),
                    contact_page_url = COALESCE(:contact_url, contact_page_url),
                    has_active_projects = :has_projects,
                    project_count = :project_count,
                    project_names = COALESCE(:project_names, project_names),
                    lead_score = :score,
                    lead_priority = :priority,
                    company_intelligence = COALESCE(:intelligence, company_intelligence),
                    last_seen = NOW()
                WHERE id = :id
            """, {
                "id": company_id,
                "website": data.get("website"),
                "phone": data.get("phone"),
                "email": data.get("email"),
                "address": data.get("address"),
                "city": data.get("city"),
                "category": data.get("company_category"),
                "description": data.get("company_description"),
                "services": data.get("services"),
                "contact_url": data.get("contact_page_url"),
                "has_projects": data.get("has_active_projects", False),
                "project_count": data.get("project_count", 0),
                "project_names": data.get("project_names"),
                "score": data.get("lead_score", 0),
                "priority": data.get("lead_priority", "LOW"),
                "intelligence": data.get("company_intelligence"),
            })
            conn.commit()
            return company_id
        else:
            result = conn.execute(text("""
                INSERT INTO companies (
                    company_name, website, phone, email, address, city,
                    company_category, company_description, services,
                    contact_page_url, source_url, has_active_projects,
                    project_count, project_names, lead_score,
                    lead_priority, company_intelligence
                ) VALUES (
                    :name, :website, :phone, :email, :address, :city,
                    :category, :description, :services,
                    :contact_url, :source, :has_projects,
                    :project_count, :project_names, :score,
                    :priority, :intelligence
                ) RETURNING id
            """), {
                "name": data["company_name"],
                "website": data.get("website"),
                "phone": data.get("phone"),
                "email": data.get("email"),
                "address": data.get("address"),
                "city": data.get("city"),
                "category": data.get("company_category"),
                "description": data.get("company_description"),
                "services": data.get("services"),
                "contact_url": data.get("contact_page_url"),
                "source": data.get("source_url", ""),
                "has_projects": data.get("has_active_projects", False),
                "project_count": data.get("project_count", 0),
                "project_names": data.get("project_names"),
                "score": data.get("lead_score", 0),
                "priority": data.get("lead_priority", "LOW"),
                "intelligence": data.get("company_intelligence"),
            })
            conn.commit()
            return result.fetchone()[0]


def insert_project(engine, company_id: int, name: str, url: str = None, source: str = None):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO projects (company_id, project_name, project_url, source_url)
            VALUES (:company_id, :name, :url, :source)
        """), {"company_id": company_id, "name": name, "url": url, "source": source})
        conn.commit()


def insert_contact(engine, company_id: int, contact_type: str, value: str, source: str = None):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO contacts (company_id, contact_type, contact_value, source_url)
            VALUES (:company_id, :type, :value, :source)
        """), {"company_id": company_id, "type": contact_type, "value": value, "source": source})
        conn.commit()


def get_all_companies(engine) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM companies ORDER BY lead_score DESC", engine)


def get_qualified_leads(engine) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT * FROM companies WHERE lead_priority IN ('HOT', 'WARM') ORDER BY lead_score DESC",
        engine
    )


def get_summary(engine) -> dict:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM v_lead_summary")).fetchone()
        if row:
            cols = ["total_companies", "with_website", "with_email", "with_phone",
                     "with_projects", "hot_leads", "warm_leads", "low_leads", "avg_score"]
            return dict(zip(cols, row))
        return {}


if __name__ == "__main__":
    print("Initializing schema...")
    init_schema()
    print("Done.")
