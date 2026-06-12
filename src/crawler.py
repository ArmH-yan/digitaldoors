"""
Lead Generation Scraper — Crawler
Multi-agent parallel crawler for construction.am
"""

import time
import random
import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "0.5"))
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "15"))
SCRAPE_MAX_RETRIES = int(os.getenv("SCRAPE_MAX_RETRIES", "2"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]

BASE_URL = "https://www.construction.am"

ARMENIAN_LETTERS = [
    "%D4%B1", "%D4%B2", "%D4%B3", "%D4%B4", "%D4%B5",
]

LISTING_PAGES = [
    "/arm/developers.php",
    "/arm/construction.php",
    "/arm/suppliers.php",
]


class ScrapingAgent:
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.user_agent = USER_AGENTS[agent_id % len(USER_AGENTS)]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self.requests_made = 0

    def fetch(self, url: str, retries: int = SCRAPE_MAX_RETRIES) -> str | None:
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=SCRAPE_TIMEOUT)
                resp.raise_for_status()
                self.requests_made += 1
                return resp.text
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(1)
        return None


def create_agents(count: int) -> list[ScrapingAgent]:
    return [ScrapingAgent(i) for i in range(count)]


def parse_company_links(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    for item in soup.find_all("div", class_="post-item"):
        link = item.find("a", href=True)
        if link and "/companies/" in link["href"]:
            full_url = urljoin(base_url, link["href"])
            name = item.get_text(strip=True).split("Դիտdelays")[0].strip()
            name = re.sub(r'\d+$', '', name).strip()
            companies.append({"url": full_url, "name": name if name else None})
    return companies


def parse_company_profile(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {"source_url": url}

    # Company name from h3 > a inside page-title
    title_div = soup.find("div", class_="page-title")
    if title_div:
        h3_link = title_div.find("h3")
        if h3_link:
            a_tag = h3_link.find("a")
            if a_tag:
                data["company_name"] = a_tag.get_text(strip=True)
            else:
                data["company_name"] = h3_link.get_text(strip=True)

    # Fallback to H1
    if not data.get("company_name"):
        h1 = soup.find("h1")
        if h1:
            data["company_name"] = h1.get_text(strip=True)

    # Phone numbers from tel: links
    phones = []
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("tel:"):
            phone = a["href"].replace("tel:", "").strip()
            if phone and len(phone) > 5:
                phones.append(phone)
    if phones:
        data["phone"] = phones[0]

    # Website from button with "Կayq" text
    for a in soup.find_all("a", href=True, class_="button"):
        if "Կayq" in a.get_text() or "Կ" in a.get_text():
            href = a["href"]
            if href.startswith("http") and "construction.am" not in href:
                data["website"] = href
                break

    # Fallback: any external link that's not analytics
    if not data.get("website"):
        skip_domains = ["construction.am", "facebook", "instagram", "yandex",
                        "mail.ru", "rambler", "google", "liveinternet"]
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and not any(d in href for d in skip_domains):
                data["website"] = href
                break

    # Meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        data["company_description"] = meta.get("content", "")

    # City from text
    text = soup.get_text()
    if "Yerevan" in text or "Երևdelays" in text:
        data["city"] = "Yerevan"
    elif "Gyumri" in text or "Գyumri" in text:
        data["city"] = "Gyumri"
    elif "Vanadzor" in text or "Վdelays" in text:
        data["city"] = "Vanadzor"

    # Services from post-item
    item = soup.find("div", class_="post-item")
    if item:
        item_text = item.get_text(strip=True)
        if "Դիտdelays" in item_text:
            category_part = item_text.split("Դիտdelays")[0]
            if data.get("company_name") and category_part.startswith(data["company_name"]):
                category_part = category_part[len(data["company_name"]):].strip()
            # Remove numbers and extra info
            category_part = re.sub(r'\d+', '', category_part).strip()
            if category_part:
                data["services"] = category_part

    return data


def crawl_company_website(agent: ScrapingAgent, website_url: str) -> dict:
    result = {"projects": [], "all_text": []}
    for path in ["/", "/about", "/projects", "/contact"]:
        url = urljoin(website_url, path)
        html = agent.fetch(url, retries=1)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for elem in soup(["script", "style"]):
                elem.decompose()
            text = soup.get_text(separator=" ", strip=True)[:2000]
            result["all_text"].append(text)
        time.sleep(0.2)
    result["full_text"] = " ".join(result["all_text"])
    return result


def _fetch_profile(args: tuple) -> dict | None:
    link, agent = args
    html = agent.fetch(link["url"])
    if html:
        data = parse_company_profile(html, link["url"])
        if not data.get("company_name") and link.get("name"):
            data["company_name"] = link["name"]
        return data
    return None


def _enrich_company(args: tuple) -> dict:
    company, agent = args
    website = company.get("website")
    if website:
        if not website.startswith(("http://", "https://")):
            website = "https://" + website
            company["website"] = website
        web_data = crawl_company_website(agent, website)
        if web_data.get("full_text"):
            company["_all_text"] = web_data["full_text"]
    return company


def run_crawler(num_agents: int = MAX_WORKERS) -> list[dict]:
    agents = create_agents(num_agents)
    print(f"  Created {num_agents} scraping agents")

    all_company_links = []

    # Phase 1: Crawl listing pages
    print("[1/3] Crawling listing pages...")
    for listing_page in LISTING_PAGES:
        print(f"\n  Source: {listing_page}")
        base_url = BASE_URL + listing_page
        html = agents[0].fetch(base_url)
        if not html:
            continue

        companies = parse_company_links(html, BASE_URL)
        all_company_links.extend(companies)
        print(f"    Page 1: Found {len(companies)} companies")

        for i, letter in enumerate(ARMENIAN_LETTERS):
            page_url = f"{BASE_URL}{listing_page}?letter={letter}"
            html = agents[(i + 1) % num_agents].fetch(page_url)
            if html:
                companies = parse_company_links(html, BASE_URL)
                all_company_links.extend(companies)
                if companies:
                    print(f"    Letter {i + 1}: Found {len(companies)} companies")
            time.sleep(SCRAPE_DELAY)

    # Deduplicate
    seen_urls = set()
    unique_links = []
    for c in all_company_links:
        if c["url"] not in seen_urls:
            seen_urls.add(c["url"])
            unique_links.append(c)
    all_company_links = unique_links

    print(f"\n  Total unique companies: {len(all_company_links)}")

    # Phase 2: Crawl profiles in parallel
    print(f"\n[2/3] Crawling profiles with {num_agents} agents...")
    profile_args = [(link, agents[i % num_agents]) for i, link in enumerate(all_company_links)]
    companies = []

    with ThreadPoolExecutor(max_workers=num_agents) as executor:
        futures = [executor.submit(_fetch_profile, args) for args in profile_args]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result and result.get("company_name"):
                companies.append(result)
            if i % 20 == 0 or i == len(futures):
                print(f"  Progress: {i}/{len(futures)}")

    # Phase 3: Enrich
    print(f"\n[3/3] Enriching {len(companies)} companies...")
    enrich_args = [(company, agents[i % num_agents]) for i, company in enumerate(companies)]

    with ThreadPoolExecutor(max_workers=num_agents) as executor:
        futures = [executor.submit(_enrich_company, args) for args in enrich_args]
        companies = [f.result() for f in as_completed(futures)]

    total_requests = sum(a.requests_made for a in agents)
    print(f"\n  Stats: {total_requests} requests across {num_agents} agents")

    return companies


if __name__ == "__main__":
    companies = run_crawler()
    print(f"\nCrawled {len(companies)} companies")
    for c in companies[:10]:
        print(f"  - {c.get('company_name')}: {c.get('website', 'no website')}")
