"""
Lead Generation Scraper — Scoring
Simple lead scoring based on company data.
"""

import re


SCORING_RULES = {
    "residential": 20,
    "commercial": 25,
    "industrial": 30,
    "parking": 20,
    "garage": 20,
    "warehouse": 15,
    "logistics": 15,
    "projects_bonus": 20,
    "has_website": 5,
    "has_email": 5,
    "has_phone": 5,
}

HOT_THRESHOLD = 60
WARM_THRESHOLD = 30


def score_company(company: dict) -> dict:
    """Calculate lead score and priority."""
    score = 0
    text = _get_analysis_text(company).lower()

    # Residential construction (English + Armenian)
    if any(kw in text for kw in ["residential", "apartment", "housing", "բնակելի", "բdelays", "բnakdelays"]):
        score += SCORING_RULES["residential"]

    # Commercial construction
    if any(kw in text for kw in ["commercial", "office", "business", "retail", "առևտրային", "գdelays", "ofis"]):
        score += SCORING_RULES["commercial"]

    # Industrial construction
    if any(kw in text for kw in ["industrial", "factory", "manufacturing", "plant", "արdelays", "գdelays"]):
        score += SCORING_RULES["industrial"]

    # Mentions parking
    if any(kw in text for kw in ["parking", "car park", "կdelays", "автостоянка"]):
        score += SCORING_RULES["parking"]

    # Mentions garage
    if any(kw in text for kw in ["garage", "гараж", "delays"]):
        score += SCORING_RULES["garage"]

    # Mentions warehouse
    if any(kw in text for kw in ["warehouse", "storage", "depot", "склад", "պdelays"]):
        score += SCORING_RULES["warehouse"]

    # Mentions logistics
    if any(kw in text for kw in ["logistics", "distribution", "supply chain", "логистика"]):
        score += SCORING_RULES["logistics"]

    # Construction keywords (Armenian)
    if any(kw in text for kw in ["շdelays", "կdelays", "նdelays", "շիdelays"]):
        score += 10

    # Developer keywords
    if any(kw in text for kw in ["developer", "դelays", "կdelays"]):
        score += 10

    if company.get("project_count", 0) > 3:
        score += SCORING_RULES["projects_bonus"]

    if company.get("website"):
        score += SCORING_RULES["has_website"]

    if company.get("email"):
        score += SCORING_RULES["has_email"]

    if company.get("phone"):
        score += SCORING_RULES["has_phone"]

    score = min(score, 100)

    if score >= HOT_THRESHOLD:
        priority = "HOT"
    elif score >= WARM_THRESHOLD:
        priority = "WARM"
    else:
        priority = "LOW"

    company["lead_score"] = score
    company["lead_priority"] = priority
    company["has_active_projects"] = company.get("project_count", 0) > 0

    return company


def generate_intelligence(company: dict) -> str:
    """Generate brief intelligence summary."""
    name = company.get("company_name", "Unknown")
    city = company.get("city", "Unknown location")
    project_count = company.get("project_count", 0)
    score = company.get("lead_score", 0)

    text = _get_analysis_text(company).lower()
    focus = []
    if any(kw in text for kw in ["residential", "apartment"]):
        focus.append("residential")
    if any(kw in text for kw in ["commercial", "office"]):
        focus.append("commercial")
    if any(kw in text for kw in ["industrial", "factory"]):
        focus.append("industrial")
    if any(kw in text for kw in ["parking", "garage"]):
        focus.append("parking/garage")

    focus_str = " and ".join(focus) if focus else "general construction"

    summary = f"{name} is a {focus_str} company based in {city}."
    if project_count > 0:
        summary += f" Active on {project_count} project(s)."
    if score >= HOT_THRESHOLD:
        summary += " Strong candidate for sectional garage doors, industrial doors, and loading dock systems."
    elif score >= WARM_THRESHOLD:
        summary += " Good candidate for door and gate systems."
    else:
        summary += " May be interested in basic door systems."

    return summary


def _get_analysis_text(company: dict) -> str:
    fields = [
        company.get("company_name", ""),
        company.get("company_description", ""),
        company.get("services", ""),
        company.get("project_names", ""),
        company.get("_all_text", ""),
    ]
    return " ".join(str(f) for f in fields if f)


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    cleaned = re.sub(r'[^\d+\-\(\)\s]', '', phone.strip())
    if cleaned.startswith("374") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    return cleaned


def normalize_email(email: str) -> str:
    if not email:
        return ""
    email = email.strip().lower()
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return email
    return ""


def normalize_website(website: str) -> str:
    if not website:
        return ""
    website = website.strip()
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    return website.rstrip("/")


def normalize_company(company: dict) -> dict:
    """Normalize all fields."""
    company["phone"] = normalize_phone(company.get("phone", ""))
    company["email"] = normalize_email(company.get("email", ""))
    company["website"] = normalize_website(company.get("website", ""))
    company.pop("_all_text", None)
    return company
