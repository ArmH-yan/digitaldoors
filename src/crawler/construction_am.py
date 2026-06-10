"""Web crawler for construction.am and company websites."""

import asyncio
import random
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from src.parsers.html_parser import CompanyListParser, CompanyProfileParser, WebsiteParser
from src.utils.logging import get_logger
from src.utils.retry import RateLimiter, retry_async

logger = get_logger("crawler")


class ConstructionAmCrawler:
    """Crawler for construction.am website."""
    
    def __init__(self, config: dict):
        self.config = config
        self.base_url = config["crawler"]["primary_source"]
        self.listing_parser = CompanyListParser(self.base_url)
        self.profile_parser = CompanyProfileParser(self.base_url)
        self.rate_limiter = RateLimiter(
            requests_per_second=1.0 / config["crawler"]["rate_limit_delay"]
        )
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
    
    async def start(self):
        """Initialize Playwright browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.config["crawler"]["headless"]
        )
        self.context = await self.browser.new_context(
            user_agent=random.choice(self.config["crawler"]["user_agents"]),
            viewport={"width": 1920, "height": 1080},
            locale="en-US"
        )
        logger.info("Browser initialized")
    
    async def stop(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed")
    
    async def _get_page(self) -> Page:
        """Get a new page with random user agent."""
        page = await self.context.new_page()
        page.set_default_timeout(self.config["crawler"]["navigation_timeout"])
        return page
    
    @retry_async(max_retries=3, delay=2.0)
    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with rate limiting and retry."""
        await self.rate_limiter.acquire()
        
        page = await self._get_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
            if response and response.status == 200:
                # Wait for dynamic content
                await page.wait_for_timeout(2000)
                content = await page.content()
                logger.debug(f"Fetched: {url}")
                return content
            else:
                status = response.status if response else "no response"
                logger.warning(f"Failed to fetch {url}: status={status}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise
        finally:
            await page.close()
    
    async def crawl_listing_pages(self) -> List[Dict]:
        """Crawl all listing pages to find company URLs."""
        all_companies = []
        current_url = self.base_url
        page_num = 1
        max_pages = self.config["crawler"].get("max_listing_pages", 50)
        
        while current_url and page_num <= max_pages:
            logger.info(f"Crawling listing page {page_num}: {current_url}")
            
            html = await self._fetch_page(current_url)
            if not html:
                break
            
            companies = self.listing_parser.parse_listing_page(html)
            all_companies.extend(companies)
            
            logger.info(f"Found {len(companies)} companies on page {page_num}")
            
            # Get next page
            current_url = self.listing_parser.get_next_page_url(html)
            page_num += 1
            
            # Small delay between pages
            await asyncio.sleep(1)
        
        logger.info(f"Total companies found: {len(all_companies)}")
        return all_companies
    
    async def crawl_company_profile(self, company_url: str) -> Optional[Dict]:
        """Crawl individual company profile page."""
        html = await self._fetch_page(company_url)
        if not html:
            return None
        
        data = self.profile_parser.parse_profile(html, company_url)
        data["source_url"] = company_url
        data["raw_html"] = html
        
        return data


class WebsiteCrawler:
    """Crawl company websites for enrichment data."""
    
    def __init__(self, config: dict):
        self.config = config
        self.website_parser = WebsiteParser()
        self.rate_limiter = RateLimiter(
            requests_per_second=1.0 / config["crawler"]["rate_limit_delay"]
        )
        self.browser: Optional[Browser] = None
    
    async def start(self):
        """Initialize browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.config["crawler"]["headless"]
        )
        logger.info("Website crawler browser initialized")
    
    async def stop(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    @retry_async(max_retries=2, delay=1.0)
    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with rate limiting."""
        await self.rate_limiter.acquire()
        
        context = await self.browser.new_context(
            user_agent=random.choice(self.config["crawler"]["user_agents"]),
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            if response and response.status == 200:
                await page.wait_for_timeout(1500)
                content = await page.content()
                return content
            return None
        except Exception as e:
            logger.debug(f"Error fetching website {url}: {e}")
            return None
        finally:
            await page.close()
            await context.close()
    
    async def crawl_company_website(self, website_url: str) -> Dict:
        """Crawl a company's website pages."""
        result = {
            "pages_crawled": 0,
            "projects": [],
            "text_content": [],
            "emails": [],
            "phones": [],
        }
        
        pages_to_check = self.config["enrichment"]["pages_to_check"]
        max_pages = self.config["enrichment"]["max_pages_per_company"]
        
        for page_path in pages_to_check[:max_pages]:
            url = urljoin(website_url, page_path)
            html = await self._fetch_page(url)
            
            if html:
                result["pages_crawled"] += 1
                text = self.website_parser.extract_text_content(html)
                result["text_content"].append(text)
                
                # Extract projects
                projects = self.website_parser.extract_projects(html, url)
                result["projects"].extend(projects)
                
                # Extract emails from page
                import re
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                emails = re.findall(email_pattern, text)
                result["emails"].extend(emails)
                
                # Extract phones from page
                phone_pattern = r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
                phones = re.findall(phone_pattern, text)
                result["phones"].extend(phones)
            
            await asyncio.sleep(0.5)
        
        # Deduplicate
        result["emails"] = list(set(result["emails"]))
        result["phones"] = list(set(result["phones"]))
        result["projects"] = result["projects"][:20]  # Limit projects
        
        return result
