-- ===========================================================================
-- Lead Generation — PostgreSQL Schema
-- ===========================================================================

-- 1. Core Tables -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS companies (
    id                SERIAL       PRIMARY KEY,
    company_name      VARCHAR(500) NOT NULL,
    website           VARCHAR(500),
    phone             VARCHAR(100),
    email             VARCHAR(255),
    address           TEXT,
    city              VARCHAR(255),
    company_category  VARCHAR(255),
    company_description TEXT,
    services          TEXT,
    contact_page_url  VARCHAR(500),
    source_url        VARCHAR(500),
    has_active_projects BOOLEAN DEFAULT FALSE,
    project_count     INTEGER DEFAULT 0,
    project_names     TEXT,
    lead_score        INTEGER DEFAULT 0,
    lead_priority     VARCHAR(10) DEFAULT 'LOW',
    company_intelligence TEXT,
    first_seen        TIMESTAMPTZ DEFAULT NOW(),
    last_seen         TIMESTAMPTZ DEFAULT NOW(),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE companies IS 'Discovered construction companies with lead scoring.';

CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name_source
    ON companies (company_name, source_url);


CREATE TABLE IF NOT EXISTS projects (
    id                  SERIAL       PRIMARY KEY,
    company_id          INTEGER      REFERENCES companies(id) ON DELETE CASCADE,
    project_name        VARCHAR(500) NOT NULL,
    project_description TEXT,
    project_url         VARCHAR(500),
    source_url          VARCHAR(500),
    detected_at         TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE projects IS 'Detected construction projects per company.';


CREATE TABLE IF NOT EXISTS contacts (
    id            SERIAL       PRIMARY KEY,
    company_id    INTEGER      REFERENCES companies(id) ON DELETE CASCADE,
    contact_type  VARCHAR(50)  NOT NULL,
    contact_value VARCHAR(500) NOT NULL,
    is_primary    BOOLEAN DEFAULT FALSE,
    source_url    VARCHAR(500)
);

COMMENT ON TABLE contacts IS 'Contact information per company.';


CREATE TABLE IF NOT EXISTS crawl_runs (
    id                 SERIAL       PRIMARY KEY,
    source_url         VARCHAR(500),
    companies_found    INTEGER DEFAULT 0,
    companies_enriched INTEGER DEFAULT 0,
    started_at         TIMESTAMPTZ DEFAULT NOW(),
    finished_at        TIMESTAMPTZ,
    status             VARCHAR(50) DEFAULT 'running',
    error_message      TEXT
);

COMMENT ON TABLE crawl_runs IS 'Crawl run metadata for tracking.';


-- 2. Indexes ----------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_companies_priority ON companies(lead_priority);
CREATE INDEX IF NOT EXISTS idx_companies_score    ON companies(lead_score);
CREATE INDEX IF NOT EXISTS idx_companies_city     ON companies(city);
CREATE INDEX IF NOT EXISTS idx_projects_company   ON projects(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_company   ON contacts(company_id);


-- 3. Views ------------------------------------------------------------------

CREATE OR REPLACE VIEW v_qualified_leads AS
SELECT
    c.*,
    COUNT(DISTINCT p.id) AS detected_projects,
    COUNT(DISTINCT ct.id) AS contact_count
FROM companies c
LEFT JOIN projects p ON c.id = p.company_id
LEFT JOIN contacts ct ON c.id = ct.company_id
WHERE c.lead_priority IN ('HOT', 'WARM')
GROUP BY c.id
ORDER BY c.lead_score DESC;

COMMENT ON VIEW v_qualified_leads IS 'Pre-filtered HOT and WARM leads.';


CREATE OR REPLACE VIEW v_lead_summary AS
SELECT
    COUNT(*) AS total_companies,
    COUNT(*) FILTER (WHERE website IS NOT NULL AND website != '') AS with_website,
    COUNT(*) FILTER (WHERE email IS NOT NULL AND email != '') AS with_email,
    COUNT(*) FILTER (WHERE phone IS NOT NULL AND phone != '') AS with_phone,
    COUNT(*) FILTER (WHERE has_active_projects = TRUE) AS with_projects,
    COUNT(*) FILTER (WHERE lead_priority = 'HOT') AS hot_leads,
    COUNT(*) FILTER (WHERE lead_priority = 'WARM') AS warm_leads,
    COUNT(*) FILTER (WHERE lead_priority = 'LOW') AS low_leads,
    ROUND(AVG(lead_score), 1) AS avg_score
FROM companies;

COMMENT ON VIEW v_lead_summary IS 'Aggregate lead statistics.';
