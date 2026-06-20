"""
Lead Generation — Defanse Housing Ecosystem Scraper
Targeted scrape of defansehousing.com partner ecosystem.
"""

import time
import re
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.crawler import USER_AGENTS, compute_content_hash

log = logging.getLogger("leadgen")

BASE_URL = "https://defansehousing.com"
DELAY = 1.8

SEED = [
    {
        "company_name": "Defanse Housing Invest CJSC",
        "company_category": "developer",
        "services": "Developer / Project Owner",
        "phone": "+374 95 020 020",
        "email": "info@defansehousing.com",
        "website": "https://defansehousing.com",
        "address": "Armenia, Yerevan, North Ave. 8/8",
        "city": "Yerevan",
        "facebook_url": "https://www.facebook.com/defansehousing",
        "instagram_url": "https://www.instagram.com/defanse_housing/",
        "linkedin_url": "https://www.linkedin.com/company/defanse-housing-invest/",
        "source_url": "https://defansehousing.com/en/contacts",
        "source_site": "defansehousing",
        "notes": "WhatsApp: +374 43 995 000. Tours Sat+Sun. Contact form has 'Cooperation offer' option.",
    },
    {
        "company_name": "Shinvector",
        "company_category": "construction",
        "services": "Construction Partner \u2013 Phase 1",
        "source_url": "https://defansehousing.com/en/partner/6",
        "source_site": "defansehousing",
    },
    {
        "company_name": "HAEKSHIN",
        "company_category": "construction",
        "services": "Construction Partner",
        "source_url": "https://defansehousing.com/en/partner/7",
        "source_site": "defansehousing",
    },
    {
        "company_name": "Horizon 95",
        "company_category": "construction",
        "services": "Construction Partner",
        "source_url": "https://defansehousing.com/en/partner/8",
        "source_site": "defansehousing",
    },
    {
        "company_name": "OST-SHIN",
        "company_category": "construction",
        "services": "Construction Partner",
        "source_url": "https://defansehousing.com/en/partner/9",
        "source_site": "defansehousing",
    },
    {
        "company_name": "Armproject (6 studios)",
        "company_category": "architecture",
        "services": "Zoning / Architectural Design",
        "address": "Yerevan, Armenia",
        "city": "Yerevan",
        "source_url": "https://defansehousing.com/en/about-us",
        "source_site": "defansehousing",
        "company_description": (
            "Zoning project commissioned from 6 studios under Armproject. "
            "Architectural council: Hrachya Poghosyan, Narek Sargsyan, "
            "Artur Meschyan, Razmik Minasyan, Alik Zurabyan (+ others)."
        ),
    },
]

ARCHITECTS = [
    "Hrachya Poghosyan",
    "Narek Sargsyan",
    "Artur Meschyan",
    "Razmik Minasyan",
    "Alik Zurabyan",
]

PARTNER_PAGES = [6, 7, 8, 9]

PHONE_RE = re.compile(r"\+374[\d\s\-()]{6,15}")
EMAIL_RE = re.compile(r"[\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,}")
ARCHITECT_RE = re.compile(
    r"((?:[A-Z][a-z]+ ){1,2}[A-Z][a-z]+)(?=\s*[,\.\u055d]?\s*(?:architect|Architect|\u0577\u056b\u0576\u0561\u0580\u0561\u0584\u0561\u0576))",
    re.UNICODE,
)


class DefanseHousingScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def fetch(self, url: str) -> str | None:
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            log.warning(f"    defanse_housing: HTTP error fetching {url}: {e}")
            return None

    def _scrape_partner_detail(self, url: str) -> dict:
        """Extract phone, email, website from a partner detail page."""
        data = {}
        html = self.fetch(url)
        if not html:
            return data

        phones = PHONE_RE.findall(html)
        if phones:
            data["phone"] = phones[0].strip()

        emails = EMAIL_RE.findall(html)
        if emails:
            data["email"] = emails[0].strip()

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "defansehousing" not in href:
                data["website"] = href
                break

        return data

    def _scrape_about_us(self) -> list[str]:
        """Extract named architects from About Us page."""
        url = f"{BASE_URL}/en/about-us"
        html = self.fetch(url)
        if not html:
            return list(ARCHITECTS)

        matches = ARCHITECT_RE.findall(html)
        names = [m.strip() for m in matches if m.strip()]
        if names:
            seen = set()
            unique = []
            for n in names:
                if n not in seen:
                    seen.add(n)
                    unique.append(n)
            return unique

        return list(ARCHITECTS)

    def _scrape_contacts(self) -> dict:
        """Extract developer contact info from Contacts page."""
        url = f"{BASE_URL}/en/contacts"
        data = {}
        html = self.fetch(url)
        if not html:
            return data

        phones = PHONE_RE.findall(html)
        if phones:
            data["phone"] = phones[0].strip()

        emails = EMAIL_RE.findall(html)
        if emails:
            data["email"] = emails[0].strip()

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "defansehousing" not in href:
                data["website"] = href
                break

        return data

    def run(self) -> list[dict]:
        """Run the full targeted scrape. Returns list of company dicts."""
        log.info("  defanse_housing: Starting targeted ecosystem scrape")
        results = []

        # Build lookup from SEED by company_name
        seed_map = {s["company_name"]: dict(s) for s in SEED}

        # 1. Scrape partner detail pages
        for pid in PARTNER_PAGES:
            url = f"{BASE_URL}/en/partner/{pid}"
            detail = self._scrape_partner_detail(url)
            # Match to seed by source_url
            for name, entry in seed_map.items():
                if entry.get("source_url") == url:
                    for k, v in detail.items():
                        if v and not entry.get(k):
                            entry[k] = v
                    break
            time.sleep(DELAY)

        # 2. Scrape contacts page for Defanse Housing
        contacts_data = self._scrape_contacts()
        defanse = seed_map.get("Defanse Housing Invest CJSC", {})
        for k, v in contacts_data.items():
            if v and not defanse.get(k):
                defanse[k] = v
        time.sleep(DELAY)

        # 3. Scrape About Us for architects
        architect_names = self._scrape_about_us()
        armproject = seed_map.get("Armproject (6 studios)", {})
        if architect_names:
            desc_parts = []
            if armproject.get("company_description"):
                desc_parts.append(armproject["company_description"])
            else:
                desc_parts.append(
                    "Zoning project commissioned from 6 studios under Armproject."
                )
            desc_parts.append(
                "Architectural council: " + ", ".join(architect_names) + "."
            )
            armproject["company_description"] = " ".join(desc_parts)

        # 4. Build final list with content hashes
        for name, entry in seed_map.items():
            content_hash = compute_content_hash(
                entry.get("company_name", ""),
                entry.get("phone", ""),
                entry.get("source_url", ""),
            )
            entry["content_hash"] = content_hash
            results.append(entry)

        log.info(f"    defanse_housing: {len(results)} companies (seed + scraped)")
        return results
