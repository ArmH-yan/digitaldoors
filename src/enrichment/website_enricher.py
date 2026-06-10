"""Data enrichment module for company websites."""

import re
from typing import Dict, List, Optional
from src.crawler.construction_am import WebsiteCrawler
from src.parsers.html_parser import WebsiteParser
from src.utils.logging import get_logger

logger = get_logger("enrichment")


class CompanyEnricher:
    """Enrich company data by crawling their websites."""
    
    def __init__(self, config: dict):
        self.config = config
        self.website_crawler = WebsiteCrawler(config)
        self.website_parser = WebsiteParser()
    
    async def start(self):
        """Initialize website crawler."""
        await self.website_crawler.start()
    
    async def stop(self):
        """Stop website crawler."""
        await self.website_crawler.stop()
    
    async def enrich_company(self, company_data: Dict) -> Dict:
        """Enrich a company with website data."""
        website = company_data.get("website")
        
        if not website:
            logger.debug(f"No website for {company_data.get('company_name')}, skipping enrichment")
            return company_data
        
        # Normalize website URL
        if not website.startswith(("http://", "https://")):
            website = "https://" + website
            company_data["website"] = website
        
        logger.info(f"Enriching company: {company_data.get('company_name')} - {website}")
        
        try:
            website_data = await self.website_crawler.crawl_company_website(website)
            
            # Merge website data into company data
            enriched = self._merge_data(company_data, website_data)
            
            return enriched
        except Exception as e:
            logger.error(f"Error enriching {company_data.get('company_name')}: {e}")
            return company_data
    
    def _merge_data(self, company_data: Dict, website_data: Dict) -> Dict:
        """Merge website data into company data."""
        enriched = company_data.copy()
        
        # Update contact info if not already present
        if not enriched.get("email") and website_data.get("emails"):
            enriched["email"] = website_data["emails"][0]
        
        if not enriched.get("phone") and website_data.get("phones"):
            enriched["phone"] = website_data["phones"][0]
        
        # Merge projects
        existing_projects = enriched.get("project_names", "") or ""
        new_projects = [p.get("name", "") for p in website_data.get("projects", []) if p.get("name")]
        
        if new_projects:
            all_projects = list(set(existing_projects.split(", ") + new_projects))
            all_projects = [p for p in all_projects if p]  # Remove empty
            enriched["project_names"] = ", ".join(all_projects[:20])
            enriched["project_count"] = len(all_projects)
        
        # Combine all text content for analysis
        all_text = " ".join(website_data.get("text_content", []))
        enriched["_all_text"] = all_text
        
        return enriched


class DataNormalizer:
    """Normalize and clean company data."""
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number format."""
        if not phone:
            return ""
        
        # Remove non-numeric chars except + and spaces
        cleaned = re.sub(r'[^\d+\-\(\)\s]', '', phone.strip())
        
        # Armenian phone format: +374 XX XXXXXX
        if cleaned.startswith("374") and not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        
        return cleaned
    
    @staticmethod
    def normalize_email(email: str) -> str:
        """Normalize and validate email."""
        if not email:
            return ""
        
        email = email.strip().lower()
        
        # Basic email validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            return email
        
        return ""
    
    @staticmethod
    def normalize_website(website: str) -> str:
        """Normalize website URL."""
        if not website:
            return ""
        
        website = website.strip()
        
        if not website.startswith(("http://", "https://")):
            website = "https://" + website
        
        # Remove trailing slash
        website = website.rstrip("/")
        
        return website
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text content."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Limit length
        return text[:2000]
    
    def normalize_company(self, company_data: Dict) -> Dict:
        """Normalize all fields in company data."""
        normalized = company_data.copy()
        
        normalized["phone"] = self.normalize_phone(normalized.get("phone", ""))
        normalized["email"] = self.normalize_email(normalized.get("email", ""))
        normalized["website"] = self.normalize_website(normalized.get("website", ""))
        normalized["company_name"] = self.normalize_text(normalized.get("company_name", ""))
        normalized["address"] = self.normalize_text(normalized.get("address", ""))
        normalized["company_description"] = self.normalize_text(normalized.get("company_description", ""))
        
        # Remove raw HTML
        normalized.pop("raw_html", None)
        normalized.pop("_all_text", None)
        
        return normalized
