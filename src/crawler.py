"""
Lead Generation Scraper — Crawler
Simple synchronous crawler for construction.am
"""

import time
import random
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1.5"))
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "30"))
SCRAPE_MAX_RETRIES = int(os.getenv("SCRAPE_MAX_RETRIES", "3"))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]

BASE_URL = "https://www.construction.am/"


def random_delay():
    time.sleep(SCRAPE_DELAY + random.uniform(0.5, 1.5))


def fetch_page(page, url: str, retries: int = SCRAPE_MAX_RETRIES) -> str | None:
    for attempt in range(retries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=SCRAPE_TIMEOUT * 1000)
            time.sleep(1.5)
            return page.content()
        except Exception as e:
            print(f"  [WARN] Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return None


def parse_company_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    companies = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if any(p in href.lower() for p in ["/company", "/contractor", "/developer", "/builder"]):
            full_url = urljoin(BASE_URL, href)
            name = link.get_text(strip=True) or None
            companies.append({"url": full_url, "name": name})

    return companies


def parse_company_profile(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {"source_url": url}

    # Company name
    for sel in ["h1", "h1.company-name", "div.company-name", "span.company-name"]:
        elem = soup.select_one(sel)
        if elem and len(elem.get_text(strip=True)) > 1:
            data["company_name"] = elem.get_text(strip=True)
            break

    # Description
    for sel in ["div.company-description", "div.about-text", "div.description", "meta[name='description']"]:
        elem = soup.select_one(sel)
        if elem:
            data["company_description"] = elem.get("content", "") if elem.name == "meta" else elem.get_text(strip=True)
            break

    # Phone
    for sel in ["a[href^='tel:']", "span.phone", "div.phone"]:
        elem = soup.select_one(sel)
        if elem:
            data["phone"] = elem.get("href", "").replace("tel:", "").strip() if elem.name == "a" else elem.get_text(strip=True)
            break
    if "phone" not in data:
        match = re.search(r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}', soup.get_text())
        if match:
            data["phone"] = match.group(0).strip()

    # Email
    for link in soup.select("a[href^='mailto:']"):
        email = link.get("href", "").replace("mailto:", "").strip()
        if "@" in email:
            data["email"] = email
            break
    if "email" not in data:
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.get_text())
        if match:
            data["email"] = match.group(0).strip()

    # Website
    for sel in ["a.website", "a[href*='www.']", "a.company-website"]:
        elem = soup.select_one(sel)
        if elem:
            href = elem.get("href", "")
            if href and not href.startswith(("mailto:", "tel:", "#")):
                data["website"] = href
                break

    # Address
    for sel in ["div.address", "span.address", "div.company-address"]:
        elem = soup.select_one(sel)
        if elem:
            data["address"] = elem.get_text(strip=True)
            break

    # City
    if "address" in data:
        cities = ["Yerevan", "Gyumri", "Vanadzor", "Vagharshapat", "Hrazdan",
                  "Abovyan", "Kapan", "Armavir", "Artashat", "Ijevan"]
        for city in cities:
            if city.lower() in data["address"].lower():
                data["city"] = city
                break

    # Category
    for sel in ["span.category", "div.category", "span.company-type"]:
        elem = soup.select_one(sel)
        if elem:
            data["company_category"] = elem.get_text(strip=True)
            break

    # Services
    for sel in ["div.services", "ul.services", "div.service-list"]:
        elem = soup.select_one(sel)
        if elem:
            items = elem.find_all(["li", "span", "div"])
            if items:
                data["services"] = ", ".join(i.get_text(strip=True) for i in items[:20] if i.get_text(strip=True))
            else:
                data["services"] = elem.get_text(strip=True)
            break

    return data


def crawl_company_website(page, website_url: str, pages_to_check: list = None) -> dict:
    if pages_to_check is None:
        pages_to_check = ["/", "/about", "/projects", "/contact", "/services"]

    result = {"projects": [], "all_text": []}

    for path in pages_to_check:
        url = urljoin(website_url, path)
        html = fetch_page(page, url, retries=2)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for elem in soup(["script", "style", "nav", "footer"]):
                elem.decompose()
            text = soup.get_text(separator=" ", strip=True)[:5000]
            result["all_text"].append(text)

            # Extract project names
            for item in soup.select("div.project-item, div.project-card, article.project"):
                title = item.select_one("h2, h3, h4, .title")
                if title:
                    result["projects"].append(title.get_text(strip=True))

        time.sleep(0.5)

    result["projects"] = list(set(result["projects"]))[:20]
    result["full_text"] = " ".join(result["all_text"])
    return result


def run_crawler() -> list[dict]:
    """Main crawler entry point. Returns list of company dicts."""
    all_company_links = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = context.new_page()

        # Crawl listing pages
        print("[1/3] Crawling listing pages...")
        current_url = BASE_URL
        page_num = 1

        while current_url and page_num <= 50:
            print(f"  Page {page_num}: {current_url}")
            html = fetch_page(page, current_url)
            if not html:
                break

            companies = parse_company_links(html)
            all_company_links.extend(companies)
            print(f"  Found {len(companies)} company links")

            # Find next page
            soup = BeautifulSoup(html, "html.parser")
            next_link = soup.select_one("a.next, a[rel='next'], li.next a")
            current_url = urljoin(BASE_URL, next_link["href"]) if next_link and next_link.get("href") else None
            page_num += 1
            random_delay()

        # Deduplicate by URL
        seen_urls = set()
        unique_links = []
        for c in all_company_links:
            if c["url"] not in seen_urls:
                seen_urls.add(c["url"])
                unique_links.append(c)
        all_company_links = unique_links

        print(f"\n[2/3] Found {len(all_company_links)} unique companies. Crawling profiles...")

        # Crawl individual profiles
        companies = []
        for i, link in enumerate(all_company_links, 1):
            print(f"  [{i}/{len(all_company_links)}] {link['url']}")
            html = fetch_page(page, link["url"])
            if html:
                data = parse_company_profile(html, link["url"])
                if not data.get("company_name") and link.get("name"):
                    data["company_name"] = link["name"]
                if data.get("company_name"):
                    companies.append(data)
            random_delay()

        # Enrich with website data
        print(f"\n[3/3] Enriching {len(companies)} companies with website data...")
        for i, company in enumerate(companies, 1):
            website = company.get("website")
            if website:
                if not website.startswith(("http://", "https://")):
                    website = "https://" + website
                    company["website"] = website

                print(f"  [{i}/{len(companies)}] Crawling website: {website}")
                web_data = crawl_company_website(page, website)

                if web_data.get("projects"):
                    company["project_names"] = ", ".join(web_data["projects"])
                    company["project_count"] = len(web_data["projects"])

                # Merge text for scoring
                company["_all_text"] = web_data.get("full_text", "")

            random_delay()

        browser.close()

    return companies


if __name__ == "__main__":
    companies = run_crawler()
    print(f"\nCrawled {len(companies)} companies")
    for c in companies[:5]:
        print(f"  - {c.get('company_name')}: {c.get('website', 'no website')}")
