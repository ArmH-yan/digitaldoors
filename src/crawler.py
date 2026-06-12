"""
Lead Generation Scraper — Crawler v2
Multi-source parallel scraper: Playwright (JS) + BS4 (static)
"""

import time
import random
import re
import hashlib
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import requests
from playwright.sync_api import sync_playwright

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "0.5"))
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "15"))
SCRAPE_MAX_RETRIES = int(os.getenv("SCRAPE_MAX_RETRIES", "3"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]

# Source definitions
SOURCES = {
    "construction_am": {
        "base_url": "https://www.construction.am",
        "listing_pages": ["/arm/developers.php", "/arm/construction.php", "/arm/suppliers.php"],
        "type": "static",
        "letter_pagination": True,
    },
    "spyur_am": {
        "base_url": "https://www.spyur.am",
        "listing_pages": ["/am/home/advanced_search/?search=1&products_and_services=1&yp_cat3=375"],
        "type": "static",
        "letter_pagination": False,
        "page_pagination": True,
    },
    "norakaruyc_am": {
        "base_url": "https://norakaruyc.am",
        "listing_pages": ["/builders", "/developers"],
        "type": "js",
        "letter_pagination": False,
    },
}


def compute_content_hash(name: str, phone: str, url: str) -> str:
    """SHA-1 hash for dedup."""
    raw = f"{name}|{phone}|{url}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


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


class BatchBuffer:
    """Buffer that flushes every BATCH_SIZE rows or on manual flush."""
    def __init__(self, batch_size: int = BATCH_SIZE):
        self.batch_size = batch_size
        self.buffer = []

    def add(self, company: dict):
        self.buffer.append(company)
        if len(self.buffer) >= self.batch_size:
            return self.flush()
        return []

    def flush(self) -> list[dict]:
        batch = self.buffer[:]
        self.buffer = []
        return batch

    @property
    def size(self):
        return len(self.buffer)


def create_agents(count: int) -> list[ScrapingAgent]:
    return [ScrapingAgent(i) for i in range(count)]


# === construction.am parsers (static/BS4) ===

def parse_construction_am_links(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    for item in soup.find_all("div", class_="post-item"):
        link = item.find("a", href=True)
        if link and "/companies/" in link["href"]:
            full_url = urljoin(base_url, link["href"])
            name = item.get_text(strip=True)
            companies.append({"url": full_url, "name": name if name else None})
    return companies


def parse_construction_am_profile(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {"source_url": url, "source_site": "construction.am"}

    # Name from h3 in page-title
    title_div = soup.find("div", class_="page-title")
    if title_div:
        h3 = title_div.find("h3")
        if h3:
            a_tag = h3.find("a")
            data["company_name"] = (a_tag or h3).get_text(strip=True)
    if not data.get("company_name"):
        h1 = soup.find("h1")
        if h1:
            data["company_name"] = h1.get_text(strip=True)

    # Phone
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("tel:"):
            phone = a["href"].replace("tel:", "").strip()
            if phone and len(phone) > 5:
                data["phone"] = phone
                break

    # Website from button
    for a in soup.find_all("a", href=True, class_="button"):
        href = a["href"]
        if href.startswith("http") and "construction.am" not in href:
            data["website"] = href
            break
    if not data.get("website"):
        skip = ["construction.am", "facebook", "instagram", "yandex", "mail.ru", "rambler", "google", "liveinternet"]
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and not any(d in href for d in skip):
                data["website"] = href
                break

    # Description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        data["company_description"] = meta.get("content", "")

    # City
    text = soup.get_text()
    if "Yerevan" in text or "Երևdelays" in text:
        data["city"] = "Yerevan"
    elif "Gyumri" in text:
        data["city"] = "Gyumri"

    return data


# === norakaruyc.am parsers (JS/Playwright) ===

def parse_norakaruyc_links(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    for card in soup.select("div.card, div.builder-card, article, div.listing-item"):
        link = card.find("a", href=True)
        if link:
            full_url = urljoin(base_url, link["href"])
            name = card.select_one("h2, h3, h4, .title, .name")
            companies.append({
                "url": full_url,
                "name": name.get_text(strip=True) if name else link.get_text(strip=True)
            })
    return companies


def parse_norakaruyc_profile(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {"source_url": url, "source_site": "norakaruyc.am"}

    h1 = soup.find("h1")
    if h1:
        data["company_name"] = h1.get_text(strip=True)

    for a in soup.find_all("a", href=True):
        if a["href"].startswith("tel:"):
            phone = a["href"].replace("tel:", "").strip()
            if phone and len(phone) > 5:
                data["phone"] = phone
                break

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "norakaruyc" not in href and "facebook" not in href:
            data["website"] = href
            break

    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        data["company_description"] = meta.get("content", "")

    return data


# === spyur.am parsers (static/BS4) ===

def parse_spyur_am_links(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/am/companies/" in href:
            full_url = urljoin(base_url, href)
            name = a.get_text(strip=True)
            if name and len(name) > 3:
                companies.append({"url": full_url, "name": name})
    return companies


def parse_spyur_am_profile(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {"source_url": url, "source_site": "spyur.am"}

    h1 = soup.find("h1")
    if h1:
        data["company_name"] = h1.get_text(strip=True)

    for a in soup.find_all("a", href=True):
        if a["href"].startswith("tel:"):
            phone = a["href"].replace("tel:", "").strip()
            if phone and len(phone) > 5:
                data["phone"] = phone
                break

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "spyur" not in href and "facebook" not in href:
            data["website"] = href
            break

    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        data["company_description"] = meta.get("content", "")

    text = soup.get_text()
    if "\u0535\u0580\u0565\u057e\u0561\u0576" in text or "Yerevan" in text:
        data["city"] = "Yerevan"
    elif "Gyumri" in text:
        data["city"] = "Gyumri"

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
    link, agent, parser = args
    html = agent.fetch(link["url"])
    if html:
        data = parser(html, link["url"])
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


def run_source(source_key: str, source_config: dict, agents: list[ScrapingAgent], buffer: BatchBuffer) -> list[dict]:
    """Crawl a single source and add to buffer."""
    base_url = source_config["base_url"]
    listing_pages = source_config["listing_pages"]
    is_js = source_config["type"] == "js"
    use_letters = source_config.get("letter_pagination", False)

    print(f"\n  Source: {source_key} ({source_config['type']})")
    all_links = []

    if is_js:
        # Use Playwright for JS-rendered pages
        print(f"    Using Playwright for {source_key}...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = context.new_page()

            for listing_page in listing_pages:
                url = base_url + listing_page
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=SCRAPE_TIMEOUT * 1000)
                    time.sleep(2)
                    html = page.content()
                    companies = parse_norakaruyc_links(html, base_url)
                    all_links.extend(companies)
                    print(f"    {listing_page}: Found {len(companies)} companies")
                except Exception as e:
                    print(f"    Error on {listing_page}: {e}")
                time.sleep(SCRAPE_DELAY)

            browser.close()
    elif source_config.get("page_pagination"):
        # Use requests with page number pagination
        page_num = 1
        max_pages = 20
        while page_num <= max_pages:
            url = base_url + listing_pages[0].replace("advanced_search", f"advanced_search-{page_num}" if page_num > 1 else "advanced_search")
            if page_num == 1:
                url = base_url + listing_pages[0]
            html = agents[0].fetch(url)
            if not html:
                break
            companies = parse_spyur_am_links(html, base_url)
            if not companies:
                break
            all_links.extend(companies)
            print(f"      Page {page_num}: Found {len(companies)} companies")
            page_num += 1
            time.sleep(SCRAPE_DELAY)
    else:
        # Use requests for static pages
        for listing_page in listing_pages:
            print(f"    {listing_page}")
            html = agents[0].fetch(base_url + listing_page)
            if html:
                companies = parse_construction_am_links(html, base_url)
                all_links.extend(companies)
                print(f"      Page 1: Found {len(companies)} companies")

            if use_letters:
                letters = [
                    "%D4%B1", "%D4%B2", "%D4%B3", "%D4%B4", "%D4%B5",
                    "%D4%B6", "%D4%B7", "%D4%B8", "%D4%B9", "%D4%BA",
                    "%D4%BB", "%D4%BC", "%D4%BD", "%D4%BE", "%D4%BF",
                    "%D5%B0", "%D5%B1", "%D5%B2", "%D5%B3", "%D5%B4",
                    "%D5%B5", "%D5%B6", "%D5%B7", "%D5%B8", "%D5%B9",
                    "%D5%BA", "%D5%BB", "%D5%BC", "%D5%BD", "%D5%BE",
                    "%D5%BF", "%D6%80", "%D6%81", "%D6%82", "%D6%83",
                    "%D6%84", "%D6%85", "%D6%86",
                ]
                for i, letter in enumerate(letters):
                    page_url = f"{base_url}{listing_page}?letter={letter}"
                    html = agents[(i + 1) % len(agents)].fetch(page_url)
                    if html:
                        companies = parse_construction_am_links(html, base_url)
                        all_links.extend(companies)
                        if companies:
                            print(f"      Letter {i + 1}: Found {len(companies)} companies")
                    time.sleep(SCRAPE_DELAY)

    # Deduplicate links
    seen = set()
    unique = []
    for l in all_links:
        if l["url"] not in seen:
            seen.add(l["url"])
            unique.append(l)

    print(f"    Total unique links: {len(unique)}")

    # Crawl profiles
    if is_js:
        parser = parse_norakaruyc_profile
    elif source_key == "spyur_am":
        parser = parse_spyur_am_profile
    else:
        parser = parse_construction_am_profile
    profile_args = [(link, agents[i % len(agents)], parser) for i, link in enumerate(unique)]
    companies = []

    with ThreadPoolExecutor(max_workers=min(len(agents), len(unique))) as executor:
        futures = [executor.submit(_fetch_profile, args) for args in profile_args]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result and result.get("company_name"):
                # Add content hash for dedup
                result["content_hash"] = compute_content_hash(
                    result.get("company_name", ""),
                    result.get("phone", ""),
                    result.get("source_url", "")
                )
                companies.append(result)
            if i % 20 == 0 or i == len(futures):
                print(f"      Profiles: {i}/{len(futures)}")

    # Enrich
    enrich_args = [(company, agents[i % len(agents)]) for i, company in enumerate(companies)]
    with ThreadPoolExecutor(max_workers=min(len(agents), len(companies))) as executor:
        futures = [executor.submit(_enrich_company, args) for args in enrich_args]
        companies = [f.result() for f in as_completed(futures)]

    # Add to batch buffer
    flushed = 0
    for company in companies:
        batch = buffer.add(company)
        if batch:
            flushed += len(batch)

    return companies


def run_crawler(num_agents: int = MAX_WORKERS, sources: list[str] = None) -> tuple[list[dict], BatchBuffer]:
    """Main crawler. Returns all companies and the buffer for final flush."""
    agents = create_agents(num_agents)
    buffer = BatchBuffer()

    if sources is None:
        sources = list(SOURCES.keys())

    print(f"  Created {num_agents} scraping agents")
    print(f"  Sources: {', '.join(sources)}")

    all_companies = []
    for source_key in sources:
        if source_key not in SOURCES:
            print(f"  Unknown source: {source_key}")
            continue
        companies = run_source(source_key, SOURCES[source_key], agents, buffer)
        all_companies.extend(companies)

    # Final flush
    remaining = buffer.flush()
    if remaining:
        print(f"\n  Final flush: {len(remaining)} rows")

    total_requests = sum(a.requests_made for a in agents)
    print(f"\n  Total: {len(all_companies)} companies, {total_requests} requests")

    return all_companies, buffer
