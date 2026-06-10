"""Main pipeline orchestrator for the lead generation system."""

import asyncio
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.crawler.construction_am import ConstructionAmCrawler
from src.enrichment.website_enricher import CompanyEnricher, DataNormalizer
from src.scoring.lead_scorer import LeadScorer
from src.storage.database import Database
from src.exports.data_exporter import DataExporter
from src.models import Company, Project, Contact, CrawlRun
from src.utils.logging import setup_logging, get_logger

logger = get_logger("pipeline")


class LeadGenerationPipeline:
    """Main orchestrator for the lead generation pipeline."""
    
    def __init__(self, config_path: str = "config.yaml"):
        # Load configuration
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        # Setup logging
        setup_logging(
            log_level=self.config["app"]["log_level"],
            log_file=self.config["app"]["log_file"]
        )
        
        # Initialize components
        self.crawler = ConstructionAmCrawler(self.config)
        self.enricher = CompanyEnricher(self.config)
        self.normalizer = DataNormalizer()
        self.scorer = LeadScorer(self.config)
        self.db = Database(self.config["database"])
        self.exporter = DataExporter(self.config)
        
        self.companies: List[Dict] = []
    
    async def run(self):
        """Execute the full pipeline."""
        logger.info("=" * 60)
        logger.info("STARTING LEAD GENERATION PIPELINE")
        logger.info("=" * 60)
        
        run_id = None
        
        try:
            # Initialize database
            await self.db.connect()
            await self.db.init_schema()
            
            # Start crawl run
            run_id = await self.db.start_crawl_run(
                self.config["crawler"]["primary_source"]
            )
            
            # Phase 1: Crawl construction.am
            logger.info("\nPHASE 1: Crawling construction.am listings")
            companies = await self._phase1_crawl()
            
            # Phase 2: Enrich with website data
            logger.info("\nPHASE 2: Enriching company data")
            enriched_companies = await self._phase2_enrich(companies)
            
            # Phase 3: Score and prioritize
            logger.info("\nPHASE 3: Scoring leads")
            scored_companies = await self._phase3_score(enriched_companies)
            
            # Phase 4: Store in database
            logger.info("\nPHASE 4: Storing in database")
            await self._phase4_store(scored_companies)
            
            # Phase 5: Export results
            logger.info("\nPHASE 5: Exporting results")
            await self._phase5_export(scored_companies)
            
            # Finish crawl run
            await self.db.finish_crawl_run(
                run_id,
                companies_found=len(companies),
                companies_enriched=len(scored_companies),
                status="completed"
            )
            
            # Print summary
            self._print_summary(scored_companies)
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            if run_id:
                await self.db.finish_crawl_run(
                    run_id,
                    companies_found=0,
                    companies_enriched=0,
                    status="failed",
                    error_message=str(e)
                )
            raise
        finally:
            await self.crawler.stop()
            await self.enricher.stop()
            await self.db.disconnect()
    
    async def _phase1_crawl(self) -> List[Dict]:
        """Crawl company listings from construction.am."""
        await self.crawler.start()
        
        # Get company URLs from listing pages
        company_links = await self.crawler.crawl_listing_pages()
        
        # Crawl individual company profiles
        companies = []
        for i, link in enumerate(company_links, 1):
            logger.info(f"Crawling company {i}/{len(company_links)}: {link['url']}")
            
            profile_data = await self.crawler.crawl_company_profile(link["url"])
            if profile_data:
                # Use name from link if not found in profile
                if not profile_data.get("company_name") and link.get("name"):
                    profile_data["company_name"] = link["name"]
                
                companies.append(profile_data)
            
            # Progress update every 10 companies
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(company_links)} companies crawled")
        
        logger.info(f"Phase 1 complete: {len(companies)} companies found")
        return companies
    
    async def _phase2_enrich(self, companies: List[Dict]) -> List[Dict]:
        """Enrich companies with website data."""
        await self.enricher.start()
        
        enriched = []
        for i, company in enumerate(companies, 1):
            company_name = company.get("company_name", "Unknown")
            logger.info(f"Enriching {i}/{len(companies)}: {company_name}")
            
            enriched_company = await self.enricher.enrich_company(company)
            
            # Normalize data
            normalized = self.normalizer.normalize_company(enriched_company)
            enriched.append(normalized)
        
        logger.info(f"Phase 2 complete: {len(enriched)} companies enriched")
        return enriched
    
    async def _phase3_score(self, companies: List[Dict]) -> List[Dict]:
        """Score and prioritize leads."""
        scored = []
        for company in companies:
            scored_company = self.scorer.score_company(company)
            
            # Generate intelligence summary
            summary = self.scorer.generate_intelligence_summary(scored_company)
            scored_company["company_intelligence"] = summary
            
            scored.append(scored_company)
        
        # Sort by score
        scored.sort(key=lambda x: x.get("lead_score", 0), reverse=True)
        
        logger.info(f"Phase 3 complete: {len(scored)} companies scored")
        return scored
    
    async def _phase4_store(self, companies: List[Dict]):
        """Store companies in database."""
        for i, company_data in enumerate(companies, 1):
            # Create Company model
            company = Company(
                company_name=company_data.get("company_name", ""),
                website=company_data.get("website"),
                phone=company_data.get("phone"),
                email=company_data.get("email"),
                address=company_data.get("address"),
                city=company_data.get("city"),
                company_category=company_data.get("company_category"),
                company_description=company_data.get("company_description"),
                services=company_data.get("services"),
                contact_page_url=company_data.get("contact_page_url"),
                source_url=company_data.get("source_url"),
                has_active_projects=company_data.get("has_active_projects", False),
                project_count=company_data.get("project_count", 0),
                project_names=company_data.get("project_names"),
                lead_score=company_data.get("lead_score", 0),
                lead_priority=company_data.get("lead_priority", "LOW"),
                company_intelligence=company_data.get("company_intelligence"),
            )
            
            company_id = await self.db.upsert_company(company)
            
            # Store projects
            project_names = company_data.get("project_names", "")
            if project_names:
                for name in project_names.split(", "):
                    if name.strip():
                        project = Project(
                            company_id=company_id,
                            project_name=name.strip(),
                            source_url=company_data.get("source_url")
                        )
                        await self.db.insert_project(project)
            
            # Store contacts
            if company_data.get("phone"):
                contact = Contact(
                    company_id=company_id,
                    contact_type="phone",
                    contact_value=company_data["phone"],
                    is_primary=True,
                    source_url=company_data.get("source_url")
                )
                await self.db.insert_contact(contact)
            
            if company_data.get("email"):
                contact = Contact(
                    company_id=company_id,
                    contact_type="email",
                    contact_value=company_data["email"],
                    is_primary=True,
                    source_url=company_data.get("source_url")
                )
                await self.db.insert_contact(contact)
        
        logger.info(f"Phase 4 complete: {len(companies)} companies stored")
    
    async def _phase5_export(self, companies: List[Dict]):
        """Export results to files."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Export all companies
        self.exporter.export_all_companies(companies, timestamp)
        
        # Export qualified leads
        self.exporter.export_qualified_leads(companies, timestamp)
        
        # Generate summary report
        self.exporter.generate_summary_report(companies, timestamp)
        
        logger.info("Phase 5 complete: Exports generated")
    
    def _print_summary(self, companies: List[Dict]):
        """Print pipeline summary."""
        total = len(companies)
        hot = sum(1 for c in companies if c.get("lead_priority") == "HOT")
        warm = sum(1 for c in companies if c.get("lead_priority") == "WARM")
        low = sum(1 for c in companies if c.get("lead_priority") == "LOW")
        
        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total companies: {total}")
        logger.info(f"HOT leads:       {hot}")
        logger.info(f"WARM leads:      {warm}")
        logger.info(f"LOW leads:       {low}")
        logger.info("=" * 60)


async def main():
    """Entry point for the pipeline."""
    pipeline = LeadGenerationPipeline()
    await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())
