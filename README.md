# Lead Generation Scraper — Armenian Construction Companies

Automated lead generation system for identifying construction companies in Armenia that purchase door systems.

## Quick Start

### 1. Start database

```bash
docker-compose up -d
```

PostgreSQL on `localhost:5432`. DBeaver web UI on `http://localhost:8978`.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

Copy `.env.example` to `.env`:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=leadgen
DB_USER=postgres
DB_PASS=postgres
MAX_WORKERS=5
RUN_INTERVAL_HOURS=6
```

### 4. Run

```bash
# Single run
python main.py

# Automated (runs every 6 hours)
python main.py --schedule
```

## How It Works

1. **Multi-agent scraping** — 5 parallel sessions with different user agents
2. **Crawl construction.am** — Find company listings
3. **Scrape profiles** — Extract contact details in parallel
4. **Enrich websites** — Visit company sites for projects/data
5. **Score leads** — Rate 0-100 based on relevance
6. **Store in PostgreSQL** — Dedup with upsert, track changes
7. **Export** — CSV, XLSX, summary report

## Output

Files saved to `data/exports/`:

- `companies_*.csv` — All companies
- `qualified_leads_*.csv` — HOT and WARM leads
- `qualified_leads_*.xlsx` — Formatted Excel
- `summary_report_*.txt` — Statistics

## Lead Scoring

| Factor | Points |
|--------|--------|
| Residential construction | +20 |
| Commercial construction | +25 |
| Industrial construction | +30 |
| Mentions parking | +20 |
| Mentions garage | +20 |
| Mentions warehouse | +15 |
| Mentions logistics | +15 |
| More than 3 projects | +20 |
| Has website | +5 |
| Has email | +5 |
| Has phone | +5 |

**Priority:** HOT (≥60) | WARM (≥30) | LOW (<30)

## DBeaver

Access your data at `http://localhost:8978`:

- Host: `localhost`
- Port: `5432`
- Database: `leadgen`
- User: `postgres`
- Password: `postgres`

### Useful Queries

```sql
-- All HOT leads
SELECT * FROM v_qualified_leads WHERE lead_priority = 'HOT';

-- Summary stats
SELECT * FROM v_lead_summary;

-- Companies by city
SELECT city, COUNT(*) FROM companies GROUP BY city ORDER BY COUNT(*) DESC;
```

## Project Structure

```
digitaldoors/
├── src/
│   ├── database.py    # PostgreSQL (SQLAlchemy + psycopg2)
│   ├── crawler.py     # Multi-agent parallel scraper
│   ├── scoring.py     # Lead scoring
│   └── export.py      # CSV/XLSX export
├── sql/schema/
│   └── 01_schema.sql
├── data/exports/
├── main.py            # Pipeline + scheduler
├── docker-compose.yml # PostgreSQL + DBeaver
├── requirements.txt
├── .env.example
└── README.md
```
