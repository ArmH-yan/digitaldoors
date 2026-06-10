# Lead Generation Scraper - Armenian Construction Companies

Production-ready lead generation system for identifying construction companies in Armenia that are likely to purchase door systems (sectional garage doors, industrial doors, automatic gates, rolling shutters, loading dock systems).

## Target Market

- Construction companies
- Developers
- General contractors
- Companies in residential, commercial, industrial, or mixed-use building projects

## Data Sources

- Primary: https://www.construction.am/
- Modular design for adding new sources

## Features

- Automated web crawling with Playwright
- Company data extraction and normalization
- Website enrichment for additional data
- Active project detection via keyword analysis
- Lead scoring (0-100) with priority classification (HOT/WARM/LOW)
- PostgreSQL storage with change tracking
- CSV/XLSX export
- Summary report generation
- Rate limiting and retry handling
- Comprehensive logging

## Project Structure

```
digitaldoors/
├── src/
│   ├── crawler/          # Web crawlers
│   ├── parsers/          # HTML parsers
│   ├── enrichment/       # Data enrichment
│   ├── scoring/          # Lead scoring
│   ├── storage/          # Database operations
│   ├── exports/          # Data export
│   ├── utils/            # Utilities
│   ├── models.py         # Data models
│   └── pipeline.py       # Main orchestrator
├── migrations/           # SQL schemas
├── config.yaml           # Configuration
├── main.py              # Entry point
├── Dockerfile           # Docker build
├── docker-compose.yml   # Docker compose
└── requirements.txt     # Python dependencies
```

## Quick Start

### Local Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

2. Set up PostgreSQL database:
```bash
createdb leadgen
psql -d leadgen -f migrations/001_initial_schema.sql
```

3. Configure database connection in `config.yaml`

4. Run the scraper:
```bash
python main.py
```

### Docker Setup

1. Start services:
```bash
docker-compose up -d
```

2. View logs:
```bash
docker-compose logs -f scraper
```

## Configuration

Edit `config.yaml` to customize:

- Database connection settings
- Crawler behavior (rate limits, retries)
- Scoring weights and thresholds
- Export formats
- Project detection keywords

## Output Files

After running, check the `exports/` directory:

- `companies_YYYYMMDD_HHMMSS.csv` - All discovered companies
- `qualified_leads_YYYYMMDD_HHMMSS.csv` - HOT and WARM leads only
- `qualified_leads_YYYYMMDD_HHMMSS.xlsx` - Formatted Excel export
- `summary_report_YYYYMMDD_HHMMSS.txt` - Summary statistics

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
| More than 3 active projects | +20 |
| Has website | +5 |
| Has email | +5 |
| Has phone | +5 |

**Priority Classification:**
- HOT: Score >= 60
- WARM: Score >= 30
- LOW: Score < 30

## Database Schema

### Tables

- `companies` - Main company data with scoring
- `projects` - Detected construction projects
- `contacts` - Contact information
- `crawl_runs` - Crawl run metadata

### Views

- `qualified_leads` - Pre-filtered HOT/WARM leads
- `lead_summary` - Aggregate statistics

## Adding New Data Sources

1. Create a new crawler in `src/crawler/`
2. Implement the parser in `src/parsers/`
3. Register in `config.yaml`
4. Update the pipeline to include the new source

## Logging

Logs are written to both console and `logs/scraper.log`.

Log levels:
- DEBUG: Detailed debug information
- INFO: General progress updates
- WARNING: Non-critical issues
- ERROR: Failures requiring attention

## License

Proprietary - Digital Doors LLC
