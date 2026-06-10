"""PostgreSQL storage module for the lead generation system."""

import asyncpg
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from src.models import Company, Project, Contact, CrawlRun
from src.utils.logging import get_logger
from src.utils.retry import retry_async

logger = get_logger("storage")


class Database:
    """Async PostgreSQL database handler."""
    
    def __init__(self, config: dict):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create connection pool."""
        self.pool = await asyncpg.create_pool(
            host=self.config["host"],
            port=self.config["port"],
            database=self.config["name"],
            user=self.config["user"],
            password=self.config["password"],
            min_size=1,
            max_size=self.config.get("pool_size", 5)
        )
        logger.info("Database connection pool created")
    
    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def init_schema(self):
        """Initialize database schema from SQL file."""
        schema_path = "migrations/001_initial_schema.sql"
        try:
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            async with self.pool.acquire() as conn:
                await conn.execute(schema_sql)
            logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            raise
    
    @retry_async(max_retries=3, delay=1.0)
    async def upsert_company(self, company: Company) -> int:
        """Insert or update company. Returns company ID."""
        async with self.pool.acquire() as conn:
            # Check if company exists
            existing = await conn.fetchrow(
                "SELECT id FROM companies WHERE company_name = $1 AND source_url = $2",
                company.company_name, company.source_url
            )
            
            if existing:
                # Update existing
                company_id = existing["id"]
                await conn.execute("""
                    UPDATE companies SET
                        website = COALESCE($1, website),
                        phone = COALESCE($2, phone),
                        email = COALESCE($3, email),
                        address = COALESCE($4, address),
                        city = COALESCE($5, city),
                        company_category = COALESCE($6, company_category),
                        company_description = COALESCE($7, company_description),
                        services = COALESCE($8, services),
                        contact_page_url = COALESCE($9, contact_page_url),
                        has_active_projects = $10,
                        project_count = $11,
                        project_names = COALESCE($12, project_names),
                        lead_score = $13,
                        lead_priority = $14,
                        company_intelligence = COALESCE($15, company_intelligence),
                        last_seen = CURRENT_TIMESTAMP
                    WHERE id = $16
                """,
                    company.website, company.phone, company.email,
                    company.address, company.city, company.company_category,
                    company.company_description, company.services,
                    company.contact_page_url, company.has_active_projects,
                    company.project_count, company.project_names,
                    company.lead_score, company.lead_priority,
                    company.company_intelligence, company_id
                )
                logger.debug(f"Updated company: {company.company_name} (ID: {company_id})")
            else:
                # Insert new
                company_id = await conn.fetchval("""
                    INSERT INTO companies (
                        company_name, website, phone, email, address, city,
                        company_category, company_description, services,
                        contact_page_url, source_url, scrape_timestamp,
                        first_seen, last_seen, has_active_projects,
                        project_count, project_names, lead_score,
                        lead_priority, company_intelligence
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                              $12, $13, $14, $15, $16, $17, $18, $19, $20)
                    RETURNING id
                """,
                    company.company_name, company.website, company.phone,
                    company.email, company.address, company.city,
                    company.company_category, company.company_description,
                    company.services, company.contact_page_url,
                    company.source_url, company.scrape_timestamp,
                    company.first_seen, company.last_seen,
                    company.has_active_projects, company.project_count,
                    company.project_names, company.lead_score,
                    company.lead_priority, company.company_intelligence
                )
                logger.debug(f"Inserted company: {company.company_name} (ID: {company_id})")
            
            return company_id
    
    @retry_async(max_retries=3, delay=1.0)
    async def insert_project(self, project: Project) -> int:
        """Insert a project record."""
        async with self.pool.acquire() as conn:
            project_id = await conn.fetchval("""
                INSERT INTO projects (company_id, project_name, project_description,
                                      project_url, source_url, detected_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """,
                project.company_id, project.project_name,
                project.project_description, project.project_url,
                project.source_url, project.detected_at
            )
            return project_id
    
    @retry_async(max_retries=3, delay=1.0)
    async def insert_contact(self, contact: Contact) -> int:
        """Insert a contact record."""
        async with self.pool.acquire() as conn:
            contact_id = await conn.fetchval("""
                INSERT INTO contacts (company_id, contact_type, contact_value,
                                      is_primary, source_url)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """,
                contact.company_id, contact.contact_type,
                contact.contact_value, contact.is_primary,
                contact.source_url
            )
            return contact_id
    
    @retry_async(max_retries=3, delay=1.0)
    async def start_crawl_run(self, source_url: str) -> int:
        """Start a new crawl run and return its ID."""
        async with self.pool.acquire() as conn:
            run_id = await conn.fetchval("""
                INSERT INTO crawl_runs (source_url, started_at, status)
                VALUES ($1, CURRENT_TIMESTAMP, 'running')
                RETURNING id
            """, source_url)
            return run_id
    
    @retry_async(max_retries=3, delay=1.0)
    async def finish_crawl_run(self, run_id: int, companies_found: int,
                                companies_enriched: int, status: str = "completed",
                                error_message: str = None):
        """Update crawl run with completion data."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE crawl_runs SET
                    companies_found = $1,
                    companies_enriched = $2,
                    finished_at = CURRENT_TIMESTAMP,
                    status = $3,
                    error_message = $4
                WHERE id = $5
            """, companies_found, companies_enriched, status, error_message, run_id)
    
    @retry_async(max_retries=3, delay=1.0)
    async def get_company_by_name(self, name: str, source_url: str = None) -> Optional[Dict]:
        """Check if company exists by name."""
        async with self.pool.acquire() as conn:
            if source_url:
                row = await conn.fetchrow(
                    "SELECT * FROM companies WHERE company_name = $1 AND source_url = $2",
                    name, source_url
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM companies WHERE company_name = $1", name
                )
            return dict(row) if row else None
    
    @retry_async(max_retries=3, delay=1.0)
    async def get_all_companies(self) -> List[Dict]:
        """Get all companies for export."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM companies ORDER BY lead_score DESC")
            return [dict(row) for row in rows]
    
    @retry_async(max_retries=3, delay=1.0)
    async def get_qualified_leads(self) -> List[Dict]:
        """Get HOT and WARM leads for export."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM companies 
                WHERE lead_priority IN ('HOT', 'WARM')
                ORDER BY lead_score DESC
            """)
            return [dict(row) for row in rows]
    
    @retry_async(max_retries=3, delay=1.0)
    async def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM lead_summary")
            return dict(row) if row else {}
