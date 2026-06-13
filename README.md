# Lead Generation Pipeline v2

Hey, so this is a scraper I built for finding Armenian construction companies that sell door systems (sectional garage doors, industrial doors, automatic gates, loading docks, that kind of stuff). The idea is to collect leads and push them to Google Sheets so the sales team can work with them.

I'm a Junior Data Analyst/Engineer and this was a good project to learn web scraping, PostgreSQL, and building something that actually runs on a schedule. It's not perfect but it works.

## What it does

1. **Scrapes** company data from Armenian business directories (construction.am, spyur.am)
2. **Scores** each lead based on how relevant they are (door systems, construction, garages, etc.)
3. **Stores** everything temporarily in PostgreSQL
4. **Syncs** the good leads to Google Sheets
5. **Exports** CSV/XLSX files locally

The pipeline tries to grab as much as it can per company — name, phone, email, full address, city, director name, founded year, employee count, ownership type, GPS coordinates, and social media links. Not every field is available for every company, but it gets what it can.

## Architecture
```
Web sources → Crawler (Playwright + BS4) → Batch buffer → PostgreSQL → Google Sheets → Purge
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

# Multiple sources
python main.py construction_am spyur_am

# Scheduled runs (every 6 hours)
python main.py --schedule
```

## Sources

| Source | Type | Companies | Notes |
|--------|------|-----------|-------|
| construction.am | Static/BS4 | ~556 | Armenian letter pagination |
| spyur.am | Static/BS4 | ~400 | Page pagination, 16 pages |
| norakaruyc.am | Playwright | - | Angular SPA, needs JS |

## Scoring

| Priority | Score | Criteria |
|----------|-------|----------|
| HOT | 60+ | Multiple product-relevant keywords |
| WARM | 30-59 | Some relevant keywords |
| COLD | <30 | Basic match only |

Keywords are in both Armenian and English — stuff like door systems, garage doors, industrial gates, loading docks, rolling shutters, etc.

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
| lead_score | Relevance score (0-100) |
| lead_priority | HOT / WARM / COLD |

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
- norakaruyc.am is an Angular SPA, needs Playwright to render JS — still being worked on
- Emails on construction.am are hidden in popover button attributes, not displayed directly
- The pipeline deduplicates companies using a SHA-1 hash of (name + phone + source_url)
- After syncing to Google Sheets, companies can be purged from the temp PostgreSQL database
