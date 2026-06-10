-- PostgreSQL Schema for Lead Generation System
-- Tables: companies, projects, contacts, crawl_runs

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(500) NOT NULL,
    website VARCHAR(500),
    phone VARCHAR(100),
    email VARCHAR(255),
    address TEXT,
    city VARCHAR(255),
    company_category VARCHAR(255),
    company_description TEXT,
    services TEXT,
    contact_page_url VARCHAR(500),
    source_url VARCHAR(500),
    scrape_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Change tracking
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Active project detection
    has_active_projects BOOLEAN DEFAULT FALSE,
    project_count INTEGER DEFAULT 0,
    project_names TEXT,
    
    -- Scoring
    lead_score INTEGER DEFAULT 0,
    lead_priority VARCHAR(10) DEFAULT 'LOW',
    company_intelligence TEXT,
    
    -- Raw data
    raw_html TEXT,
    
    -- Unique constraint to prevent duplicates
    CONSTRAINT uq_company_name_source UNIQUE (company_name, source_url)
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    project_name VARCHAR(500) NOT NULL,
    project_description TEXT,
    project_url VARCHAR(500),
    source_url VARCHAR(500),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Contacts table
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    contact_type VARCHAR(50) NOT NULL,  -- phone, email, website
    contact_value VARCHAR(500) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    source_url VARCHAR(500)
);

-- Crawl runs table
CREATE TABLE IF NOT EXISTS crawl_runs (
    id SERIAL PRIMARY KEY,
    source_url VARCHAR(500),
    companies_found INTEGER DEFAULT 0,
    companies_enriched INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'running',
    error_message TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name);
CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city);
CREATE INDEX IF NOT EXISTS idx_companies_priority ON companies(lead_priority);
CREATE INDEX IF NOT EXISTS idx_companies_score ON companies(lead_score);
CREATE INDEX IF NOT EXISTS idx_companies_has_projects ON companies(has_active_projects);
CREATE INDEX IF NOT EXISTS idx_companies_last_seen ON companies(last_seen);

CREATE INDEX IF NOT EXISTS idx_projects_company ON projects(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type);

CREATE INDEX IF NOT EXISTS idx_crawl_runs_status ON crawl_runs(status);
CREATE INDEX IF NOT EXISTS idx_crawl_runs_started ON crawl_runs(started_at);

-- Function to update last_seen on conflict
CREATE OR REPLACE FUNCTION update_last_seen()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_seen = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for automatic last_seen update
CREATE TRIGGER trigger_update_last_seen
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_last_seen();

-- View for qualified leads
CREATE OR REPLACE VIEW qualified_leads AS
SELECT 
    c.*,
    COUNT(DISTINCT p.id) as detected_projects,
    COUNT(DISTINCT ct.id) as contact_count
FROM companies c
LEFT JOIN projects p ON c.id = p.company_id
LEFT JOIN contacts ct ON c.id = ct.company_id
WHERE c.lead_priority IN ('HOT', 'WARM')
GROUP BY c.id
ORDER BY c.lead_score DESC;

-- View for summary statistics
CREATE OR REPLACE VIEW lead_summary AS
SELECT 
    COUNT(*) as total_companies,
    COUNT(CASE WHEN website IS NOT NULL AND website != '' THEN 1 END) as companies_with_website,
    COUNT(CASE WHEN email IS NOT NULL AND email != '' THEN 1 END) as companies_with_email,
    COUNT(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 END) as companies_with_phone,
    COUNT(CASE WHEN has_active_projects = TRUE THEN 1 END) as companies_with_projects,
    COUNT(CASE WHEN lead_priority = 'HOT' THEN 1 END) as hot_leads,
    COUNT(CASE WHEN lead_priority = 'WARM' THEN 1 END) as warm_leads,
    COUNT(CASE WHEN lead_priority = 'LOW' THEN 1 END) as low_leads,
    ROUND(AVG(lead_score), 1) as avg_score
FROM companies;
