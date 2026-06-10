"""Data models for the lead generation system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class LeadPriority(Enum):
    HOT = "HOT"
    WARM = "WARM"
    LOW = "LOW"


@dataclass
class Company:
    """Core company data model."""
    company_name: str
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    company_category: Optional[str] = None
    company_description: Optional[str] = None
    services: Optional[str] = None
    contact_page_url: Optional[str] = None
    source_url: Optional[str] = None
    scrape_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Change tracking
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    
    # Active project detection
    has_active_projects: bool = False
    project_count: int = 0
    project_names: Optional[str] = None
    
    # Scoring
    lead_score: int = 0
    lead_priority: str = "LOW"
    company_intelligence: Optional[str] = None
    
    # Internal
    id: Optional[int] = None
    raw_html: Optional[str] = None


@dataclass
class Project:
    """Project data model."""
    company_id: Optional[int] = None
    project_name: str = ""
    project_description: Optional[str] = None
    project_url: Optional[str] = None
    source_url: Optional[str] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Contact:
    """Contact information data model."""
    company_id: Optional[int] = None
    contact_type: str = ""  # phone, email, website
    contact_value: str = ""
    is_primary: bool = False
    source_url: Optional[str] = None


@dataclass
class CrawlRun:
    """Crawl run metadata."""
    source_url: str = ""
    companies_found: int = 0
    companies_enriched: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    status: str = "running"
    error_message: Optional[str] = None
