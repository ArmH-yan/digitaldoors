# Lead Generation Pipeline v2

Web scraper for finding Armenian construction companies that sell door systems (sectional garage doors, industrial doors, automatic gates, loading docks, etc.). Collects leads and pushes them to Google Sheets for the sales team.

## What it does

1. **Scrapes** company data from Armenian business directories and targeted project ecosystems
2. **Scores** each lead based on relevance (door systems, construction, garages, etc.)
3. **Stores** everything temporarily in PostgreSQL
4. **Syncs** the good leads to Google Sheets (update-in-place dedup)
5. **Exports** CSV/XLSX files locally

Extracts: name, phone, email, full address, city, district, director, founded year, employee count, ownership type, GPS coordinates, social media links, services, and company intelligence summaries.

## Architecture
```
Web sources → Crawler (BS4 + targeted scrapers) → Batch buffer → PostgreSQL → Google Sheets → Purge
```

## Setup
### 1. Virtual Env.
It's important to activate venv before installing anything.
```bash
python -m venv venv

.\venv\Scripts\activate

python.exe -m pip install --upgrade pip
```

### 2. Install dependencies

Verify Playwright installed in.

```bash
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
```
Output: Playwright OK

```bash
pip install -r requirements.txt

python -m playwright install chromium --with-deps
```


### 3. Configure
```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 4. Docker (PostgreSQL)
```bash
docker-compose up -d
```

### 5. Google Sheets (optional)

To enable Google Sheets sync:

1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create a Service Account and download JSON key to `credentials/gsheets_key.json`
4. Create a Google Sheet and copy its ID
5. Add to `.env`:
   ```
   GOOGLE_SHEET_ID=your_sheet_id_here
   GOOGLE_CREDS_FILE=credentials/gsheets_key.json
   ```

## Usage

```bash
# All sources
python main.py

# Single source
python main.py construction_am
python main.py spyur_am
python main.py defanse_housing

# Multiple sources
python main.py construction_am spyur_am
python main.py defanse_housing spyur_am

# Scheduled runs (every 6 hours)
python main.py --schedule
```

### Source Selection

| Command | What runs |
|---------|-----------|
| `python main.py` | All 3 active sources (construction_am, spyur_am, defanse_housing) |
| `python main.py construction_am` | Only construction.am directory scrape |
| `python main.py spyur_am` | Only spyur.am directory scrape |
| `python main.py defanse_housing` | Only Defanse Housing ecosystem (targeted scrape) |
| `python main.py defanse_housing spyur_am` | Defanse + spyur combined |
| `python main.py --schedule` | Runs every 6 hours in a loop |

### CLI Arguments

- Positional args: source keys (space-separated) — run only those sources
- `--schedule`: run the pipeline on a recurring interval (default: every 6 hours, configurable via `RUN_INTERVAL_HOURS` in `.env`)
- No args: run all available sources once

## Sources

| Source | Type | Companies | Notes |
|--------|------|-----------|-------|
| construction.am | Static/BS4 | ~556 | Armenian letter pagination (38 letters) |
| spyur.am | Static/BS4 | ~400 | Page pagination, 20 per page |
| defanse_housing | Targeted | 6 | Partner ecosystem scrape (seed + live enrichment) |

### defanse_housing (Targeted Scraper)

Scrapes the Defanse Housing developer ecosystem — a planned district in Yerevan. Extracts:

- **Defanse Housing Invest CJSC** — the developer (phone, email, address, socials)
- **4 construction partners** — Shinvector, HAEKSHIN, Horizon 95, OST-SHIN (phone, email, website from detail pages)
- **Armproject** — architecture firm with named architects (extracted via regex from About Us page)

This scraper bypasses the standard directory flow and runs as a standalone targeted module. Each run returns seed data enriched with any live-scraped values. HTTP errors are caught and logged — the pipeline never crashes on a 403.

## Scoring

| Priority | Score | Criteria |
|----------|-------|----------|
| HOT | 60+ | Multiple product-relevant keywords |
| WARM | 30-59 | Some relevant keywords |
| COLD | <30 | Basic match only |

Keywords are in both Armenian and English — door systems, garage doors, industrial gates, loading docks, rolling shutters, residential, commercial, cold storage, warehouse, parking, logistics, etc.

### Ecosystem Categories

Defanse Housing partners are tagged with ecosystem categories:

| Category | Intelligence |
|----------|-------------|
| `developer` | Major district developer — likely buyer of access control, gates, barriers |
| `construction` | Active contractor — potential buyer of sectional/industrial doors |
| `architecture` | Design firm — early-stage influence on door/gate specifications |

## Data Collected

| Field | Description |
|-------|-------------|
| company_name | Original name from source |
| phone | Primary phone number |
| email | Business email |
| address | Full location address |
| city | Extracted city name |
| district | Administrative district (spyur.am) |
| director | Company director/owner name |
| founded_year | Year founded |
| employee_count | Employee range |
| ownership_type | Private/state/etc |
| gps_lat, gps_lon | Map coordinates |
| facebook_url, instagram_url, linkedin_url | Social media |
| company_category | Ecosystem role (developer/construction/architecture) |
| services | Company services/role description |
| lead_score | Relevance score (0-100) |
| lead_priority | HOT / WARM / COLD |
| company_intelligence | Auto-generated summary with ecosystem context |

## Exports

- `data/exports/companies_*.csv` - All companies
- `data/exports/qualified_leads_*.csv` - HOT + WARM leads
- `data/exports/qualified_leads_*.xlsx` - Same but Excel
- `data/exports/summary_report_*.txt` - Quick stats

## Logs

Every run creates a log file in `data/logs/run_*.log` with timestamps. You can see what's happening in real time — which sources are being crawled, how many profiles were fetched, errors, etc.

## Notes

- construction.am uses Armenian letter pagination (38 letters) to find company profiles
- spyur.am uses page-based pagination (20 companies per page)
- defanse_housing is a targeted scraper — runs separately from the directory flow
- Emails on construction.am are hidden in popover button attributes, not displayed directly
- The pipeline deduplicates companies using a SHA-1 hash of (name + phone + source_url)
- After syncing to Google Sheets, companies can be purged from the temp PostgreSQL database
- All HTTP errors are caught and logged — the pipeline never crashes on a 403/timeout
