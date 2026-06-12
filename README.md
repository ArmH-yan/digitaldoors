# Lead Generation Pipeline v2

Scraper for Armenian construction companies selling door systems.

## Architecture
```
Web sources → Crawler (Playwright + BS4) → Batch buffer → PostgreSQL → Google Sheets → Purge
```

## Setup

### 1. Install dependencies
```bash
pip install requests beautifulsoup4 sqlalchemy psycopg2-binary playwright gspread google-auth openpyxl
playwright install chromium
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 3. Docker (PostgreSQL)
```bash
docker-compose up -d
```

### 4. Google Sheets (optional)

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
| LOW | <30 | Basic match only |

## Exports

- `data/exports/companies_*.csv` - All companies
- `data/exports/qualified_leads_*.xlsx` - HOT + WARM leads
- `data/exports/summary_report_*.txt` - Summary statistics
