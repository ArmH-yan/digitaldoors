# Lead Generation Scraper — Armenian Construction Companies

Production-ready lead generation system for identifying construction companies in Armenia that purchase door systems (sectional garage doors, industrial doors, automatic gates, rolling shutters, loading dock systems).

## Quick Start

### 1. Start database

```bash
docker-compose up -d
```

PostgreSQL runs on `localhost:5432`. DBeaver web UI on `http://localhost:8978`.

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure

Copy `.env.example` to `.env` and edit if needed:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=leadgen
DB_USER=postgres
DB_PASS=postgres
```

### 4. Run

```bash
python main.py
```

## Output

Files are saved to `data/exports/`:

- `companies_*.csv` — All discovered companies
- `qualified_leads_*.csv` — HOT and WARM leads
- `qualified_leads_*.xlsx` — Formatted Excel export
- `summary_report_*.txt` — Summary statistics

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

## Project Structure

```
digitaldoors/
├── src/
│   ├── database.py    # PostgreSQL with SQLAlchemy
│   ├── crawler.py     # construction.am scraper
│   ├── scoring.py     # Lead scoring & normalization
│   └── export.py      # CSV/XLSX export
├── sql/
│   └── schema/
│       └── 01_schema.sql
├── data/
│   ├── raw/
│   └── exports/
├── main.py            # Pipeline entry point
├── docker-compose.yml # PostgreSQL + DBeaver
├── requirements.txt
├── .env.example
└── README.md
```

## Database

Access via DBeaver web UI at `http://localhost:8978` or any PostgreSQL client.

Connection:
- Host: `localhost`
- Port: `5432`
- Database: `leadgen`
- User: `postgres`
- Password: `postgres`

### Tables

- `companies` — Company data with lead scoring
- `projects` — Detected construction projects
- `contacts` — Contact information
- `crawl_runs` — Crawl run metadata

### Views

- `v_qualified_leads` — Pre-filtered HOT/WARM leads
- `v_lead_summary` — Aggregate statistics
