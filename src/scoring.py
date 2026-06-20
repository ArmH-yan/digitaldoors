"""
Lead Generation v2 — Scoring
Enhanced scoring with cold storage, warehouse, garage keywords.
"""

SCORING_RULES = {
    "residential": 20,
    "commercial": 25,
    "industrial": 30,
    "cold_storage": 30,
    "warehouse": 25,
    "parking": 20,
    "garage": 20,
    "logistics": 15,
    "projects_bonus": 20,
    "has_website": 5,
    "has_email": 5,
    "has_phone": 5,
}

HOT_THRESHOLD = 60
WARM_THRESHOLD = 30

# Legacy alias
COLD = "COLD"

DEFANSE_ECOSYSTEM_ROLES = {
    "developer": "Major district developer \u2014 likely buyer of access control, gates, barriers.",
    "construction": "Active contractor \u2014 potential buyer of sectional/industrial doors.",
    "architecture": "Design firm \u2014 early-stage influence on door/gate specifications.",
}

PROJECT_KEYWORDS_EN = [
    "construction", "residential complex", "apartment building",
    "new development", "project", "high-rise", "commercial center",
    "business center", "warehouse", "industrial facility", "mixed-use",
    "parking", "underground parking", "garage", "cold storage",
    "refrigeration", "storage facility", "distribution center",
    "developer", "real estate",
    "architect", "architectural design", "zoning", "project developer",
    "construction partner", "engineering firm", "designer",
    "urban development", "district planning",
]

# Armenian keywords as Unicode escapes to avoid encoding issues
# U+0577=sh, U+056B=i, U+0576=n, U+0578+U+0582=u, U+0575=y, U+0584=t'
# construction: U+0577 U+056B U+0576 U+0578 U+0582 U+057F U+0575 U+0578 U+0582 U+0576
PROJECT_KEYWORDS_HY = [
    "\u0577\u056B\u0576\u0578\u0582\u057F\u0575\u0578\u0582\u0576",   # շինություն (construction)
    "\u056F\u0561\u057C\u0578\u0582\u0575\u057D\u057F",               # կdelays (construction)
    "\u0562\u0576\u0561\u056F\u0565\u056C\u056B",                     # բdelays (residential)
    "\u0570\u0561\u057D\u057F\u0578\u0582\u0569\u0575\u0578\u0582\u0576", # հաստdelays (construction)
    "\u0571\u056B\u0576\u0578\u0582\u057F\u0575\u0578\u0582\u0576",   # ձdelays (construction)
    "\u056F\u0561\u057C\u0578\u0582\u0575\u057D\u057F\u0561\u0576\u056F\u0561\u0580", # կdelays (constructor)
    "\u0585\u0580\u056F\u0561\u0576\u0561\u057A\u0561\u057F\u0578\u0582\u0569\u0575\u0578\u0582\u0576", # delaysdelaysdelays (development)
]

# Door/gate related Armenian keywords
DOOR_KEYWORDS_HY = [
    "\u0571\u0578\u0582\u056C",      # ձdelays (door)
    "\u0564\u0578\u0582\u0581",      # դdelays (gate)
    "\u057A\u0561\u057F\u0578\u0581", # պdelays (gate)
    "\u0576\u0565\u0580\u0578\u0582\u0569\u0575\u0578\u0582\u0576", # նdelays (garage)
    "\u057A\u0561\u0570\u0565\u057D\u057F", # պdelays (storage)
    "\u057D\u0572\u0561\u0564",      # սdelays (warehouse)
]


def score_company(company: dict) -> dict:
    """Calculate lead score and priority."""
    score = 0
    text = _get_analysis_text(company).lower()

    # Residential construction
    if any(kw in text for kw in ["residential", "apartment", "housing", "\u0562\u0576\u0561\u056F\u0565\u056C\u056B"]):
        score += SCORING_RULES["residential"]

    # Commercial construction
    if any(kw in text for kw in ["commercial", "office", "business", "retail", "\u0561\u057C\u0564\u0565\u056C"]):
        score += SCORING_RULES["commercial"]

    # Industrial construction
    if any(kw in text for kw in ["industrial", "factory", "manufacturing", "plant", "\u0561\u0580\u0564\u0575\u0578\u0582\u0576\u0561\u0562\u0565\u0580\u0561\u056F\u0561\u0576"]):
        score += SCORING_RULES["industrial"]

    # Cold storage / refrigeration
    if any(kw in text for kw in ["cold storage", "refrigeration", "freezer", "\u057D\u0580\u0565\u0576\u0564", "\u057D\u0570\u0578\u0582\u0574\u0561\u0580"]):
        score += SCORING_RULES["cold_storage"]

    # Warehouse / storage
    if any(kw in text for kw in ["warehouse", "storage", "depot", "\u057D\u0572\u0561\u0564", "\u057A\u0561\u0570\u0565\u057D\u057F"]):
        score += SCORING_RULES["warehouse"]

    # Parking
    if any(kw in text for kw in ["parking", "car park", "\u056F\u0561\u0575\u0561\u0576\u0561\u057F\u0565\u056C\u056B", "\u0561\u057E\u057F\u0578\u057D\u057F\u0578\u0582\u0575\u0576\u056F\u0561"]):
        score += SCORING_RULES["parking"]

    # Garage
    if any(kw in text for kw in ["garage", "\u0563\u0561\u0580\u0561\u0566", "\u0576\u0565\u0580\u0578\u0582\u0569\u0575\u0578\u0582\u0576"]):
        score += SCORING_RULES["garage"]

    # Logistics
    if any(kw in text for kw in ["logistics", "distribution", "supply chain", "\u056C\u0578\u0563\u056B\u057D\u057F\u056B\u056F\u0561"]):
        score += SCORING_RULES["logistics"]

    # Construction keywords (Armenian)
    if any(kw in text for kw in PROJECT_KEYWORDS_HY):
        score += 10

    # Door/gate keywords (Armenian) - direct product relevance
    if any(kw in text for kw in DOOR_KEYWORDS_HY):
        score += 15

    # Developer keywords
    if any(kw in text for kw in ["developer", "\u0576\u0565\u0580\u0578\u0582\u0569\u0575\u0578\u0582\u0576\u0561\u057E\u0578\u0580", "\u056F\u0561\u057C\u0578\u0582\u0575\u057D\u057F"]):
        score += 10

    # Projects bonus
    if company.get("project_count", 0) > 3:
        score += SCORING_RULES["projects_bonus"]

    # Contact info bonus
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
        priority = "COLD"

    company["lead_score"] = score
    company["lead_priority"] = priority
    company["has_active_projects"] = _detect_projects(text)

    # Populate project_count and project_names from matched keywords
    matched = _find_project_keywords(text)
    company["project_count"] = len(matched)
    if matched:
        company["project_names"] = ", ".join(matched)

    return company


def generate_intelligence(company: dict) -> str:
    """Generate brief intelligence summary."""
    name = company.get("company_name", "Unknown")
    city = company.get("city", "Unknown location")
    project_count = company.get("project_count", 0)
    score = company.get("lead_score", 0)

    text = _get_analysis_text(company).lower()
    focus = []
    if any(kw in text for kw in ["residential", "apartment", "\u0562\u0576\u0561\u056F\u0565\u056C\u056B"]):
        focus.append("residential")
    if any(kw in text for kw in ["commercial", "office", "\u0561\u057C\u0564\u0565\u056C"]):
        focus.append("commercial")
    if any(kw in text for kw in ["industrial", "factory", "\u0561\u0580\u0564\u0575\u0578\u0582\u0576\u0561\u0562\u0565\u0580\u0561\u056F\u0561\u0576"]):
        focus.append("industrial")
    if any(kw in text for kw in ["cold storage", "refrigeration", "\u057D\u0580\u0565\u0576\u0564"]):
        focus.append("cold storage")
    if any(kw in text for kw in ["warehouse", "storage", "\u057D\u0572\u0561\u0564"]):
        focus.append("warehouse")
    if any(kw in text for kw in ["parking", "garage", "\u0576\u0565\u0580\u0578\u0582\u0569\u0575\u0578\u0582\u0576"]):
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

    role = DEFANSE_ECOSYSTEM_ROLES.get(company.get("company_category", ""))
    if role:
        summary += f" [{role}]"

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


def _detect_projects(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in PROJECT_KEYWORDS_EN + PROJECT_KEYWORDS_HY)


def _find_project_keywords(text: str) -> list[str]:
    """Find which project keywords match in the text. Returns list of matched keywords."""
    text_lower = text.lower()
    matched = []
    for kw in PROJECT_KEYWORDS_EN:
        if kw.lower() in text_lower:
            matched.append(kw)
    return matched


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    import re
    cleaned = re.sub(r'[^\d+\-\(\)\s]', '', phone.strip())
    if cleaned.startswith("374") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    return cleaned


def normalize_email(email: str) -> str:
    if not email:
        return ""
    import re
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
    company["phone"] = normalize_phone(company.get("phone", ""))
    company["email"] = normalize_email(company.get("email", ""))
    company["website"] = normalize_website(company.get("website", ""))
    company.pop("_all_text", None)
    return company
