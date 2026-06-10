"""HTML parsers for extracting company data from web pages."""

import re
from typing import Optional, List, Dict, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from src.utils.logging import get_logger

logger = get_logger("parsers")


class CompanyListParser:
    """Parse company listing pages from construction.am."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def parse_listing_page(self, html: str) -> List[Dict]:
        """Extract company links from a listing page."""
        soup = BeautifulSoup(html, "html.parser")
        companies = []
        
        # Try multiple selector patterns for company listings
        selectors = [
            "div.company-item a",
            "div.company-card a",
            "a.company-link",
            "div.listing-item a",
            "div.contractor-item a",
            "article a[href*='company']",
            "div.item a[href*='company']",
            "a[href*='/company/']",
            "a[href*='/companies/']",
            "div.contractor a",
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            if links:
                for link in links:
                    href = link.get("href", "")
                    if href:
                        full_url = urljoin(self.base_url, href)
                        company_data = {
                            "url": full_url,
                            "name": link.get_text(strip=True) or None,
                        }
                        companies.append(company_data)
                if companies:
                    break
        
        # Fallback: find all internal links that might be company pages
        if not companies:
            all_links = soup.find_all("a", href=True)
            for link in all_links:
                href = link["href"]
                if any(pattern in href.lower() for pattern in ["/company", "/contractor", "/developer", "/builder"]):
                    full_url = urljoin(self.base_url, href)
                    companies.append({
                        "url": full_url,
                        "name": link.get_text(strip=True) or None,
                    })
        
        logger.debug(f"Found {len(companies)} company links on listing page")
        return companies
    
    def get_next_page_url(self, html: str) -> Optional[str]:
        """Extract next page URL for pagination."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Try common pagination selectors
        selectors = [
            "a.next",
            "a[rel='next']",
            "li.next a",
            "a.pagination-next",
            "a:contains('Next')",
            "a:contains('Հաջորդ')",  # Armenian "Next"
        ]
        
        for selector in selectors:
            try:
                next_link = soup.select_one(selector)
                if next_link and next_link.get("href"):
                    return urljoin(self.base_url, next_link["href"])
            except Exception:
                continue
        
        return None


class CompanyProfileParser:
    """Parse individual company profile pages."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def parse_profile(self, html: str, url: str) -> Dict:
        """Extract company information from profile page."""
        soup = BeautifulSoup(html, "html.parser")
        
        data = {
            "company_name": self._extract_company_name(soup),
            "description": self._extract_description(soup),
            "phone": self._extract_phone(soup),
            "email": self._extract_email(soup),
            "website": self._extract_website(soup, url),
            "address": self._extract_address(soup),
            "city": self._extract_city(soup),
            "category": self._extract_category(soup),
            "services": self._extract_services(soup),
            "contact_page_url": self._extract_contact_page(soup, url),
        }
        
        return data
    
    def _extract_company_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company name from profile."""
        selectors = [
            "h1.company-name",
            "h1.company-title",
            "h1.title",
            "h1",
            "div.company-name",
            "span.company-name",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text and len(text) > 1:
                    return text
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company description."""
        selectors = [
            "div.company-description",
            "div.about-text",
            "div.description",
            "div.company-about",
            "p.description",
            "meta[name='description']",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                if elem.name == "meta":
                    return elem.get("content", "")
                text = elem.get_text(strip=True)
                if text:
                    return text[:2000]  # Limit length
        return None
    
    def _extract_phone(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract phone number."""
        # Try specific phone selectors
        selectors = [
            "a[href^='tel:']",
            "span.phone",
            "div.phone",
            "span.telephone",
            "div.contact-phone",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                if elem.name == "a":
                    return elem.get("href", "").replace("tel:", "").strip()
                return elem.get_text(strip=True)
        
        # Regex fallback
        text = soup.get_text()
        phone_pattern = r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
        match = re.search(phone_pattern, text)
        if match:
            return match.group(0).strip()
        
        return None
    
    def _extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract email address."""
        # Try mailto links
        mailto_links = soup.select("a[href^='mailto:']")
        for link in mailto_links:
            email = link.get("href", "").replace("mailto:", "").strip()
            if "@" in email:
                return email
        
        # Try email selectors
        selectors = [
            "span.email",
            "div.email",
            "a.email",
            "span.contact-email",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if "@" in text:
                    return text
        
        # Regex fallback
        text = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, text)
        if match:
            return match.group(0).strip()
        
        return None
    
    def _extract_website(self, soup: BeautifulSoup, page_url: str) -> Optional[str]:
        """Extract company website."""
        # Try specific website links
        selectors = [
            "a.website",
            "a[href*='www.']",
            "a.company-website",
            "a.external-link",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                href = elem.get("href", "")
                if href and not href.startswith(("mailto:", "tel:", "#", "javascript:")):
                    return href
        
        # Look for links with website icon class
        all_links = soup.find_all("a", href=True)
        for link in all_links:
            href = link["href"]
            classes = " ".join(link.get("class", []))
            if "website" in classes.lower() or "globe" in classes.lower():
                if not href.startswith(("mailto:", "tel:", "#", "javascript:", page_url)):
                    return href
        
        return None
    
    def _extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract address."""
        selectors = [
            "div.address",
            "span.address",
            "div.company-address",
            "p.address",
            "div.location",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return None
    
    def _extract_city(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract city."""
        address = self._extract_address(soup)
        if address:
            # Common Armenian cities
            cities = ["Yerevan", "Gyumri", "Vanadzor", "Vagharshapat", "Hrazdan",
                      "Abovyan", "Kapan", "Armavir", "Artashat", "Ijevan",
                      "Այdelays", "Գyumri", "Վanadzor"]
            address_lower = address.lower()
            for city in cities:
                if city.lower() in address_lower:
                    return city
        
        # Try city selector
        selectors = [
            "span.city",
            "div.city",
            "span.location-city",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        
        return None
    
    def _extract_category(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company category."""
        selectors = [
            "span.category",
            "div.category",
            "span.company-type",
            "div.company-type",
            "span.badge",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return None
    
    def _extract_services(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract services offered."""
        selectors = [
            "div.services",
            "ul.services",
            "div.service-list",
            "div.company-services",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                items = elem.find_all(["li", "span", "div"])
                if items:
                    services = [item.get_text(strip=True) for item in items if item.get_text(strip=True)]
                    return ", ".join(services[:20])  # Limit to 20 services
                return elem.get_text(strip=True)
        return None
    
    def _extract_contact_page(self, soup: BeautifulSoup, page_url: str) -> Optional[str]:
        """Extract contact page URL."""
        all_links = soup.find_all("a", href=True)
        for link in all_links:
            href = link["href"].lower()
            if any(p in href for p in ["/contact", "/contact-us", "/kapcsolat"]):
                return urljoin(page_url, link["href"])
        return None


class WebsiteParser:
    """Parse company website pages for enrichment."""
    
    def extract_projects(self, html: str, url: str) -> List[Dict]:
        """Extract project information from website page."""
        soup = BeautifulSoup(html, "html.parser")
        projects = []
        
        # Look for project cards/items
        selectors = [
            "div.project-item",
            "div.project-card",
            "article.project",
            "div.portfolio-item",
            "div.work-item",
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            for item in items:
                title_elem = item.select_one("h2, h3, h4, .title, .project-name")
                desc_elem = item.select_one("p, .description, .project-desc")
                link_elem = item.select_one("a[href]")
                
                project = {
                    "name": title_elem.get_text(strip=True) if title_elem else None,
                    "description": desc_elem.get_text(strip=True)[:500] if desc_elem else None,
                    "url": urljoin(url, link_elem["href"]) if link_elem else None,
                }
                if project["name"]:
                    projects.append(project)
        
        return projects
    
    def extract_text_content(self, html: str) -> str:
        """Extract clean text content from page."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        # Limit to first 5000 chars for analysis
        return text[:5000]
