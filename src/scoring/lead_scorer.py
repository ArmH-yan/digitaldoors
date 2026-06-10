"""Lead scoring module for ranking company quality."""

from typing import Dict, List
from src.utils.logging import get_logger

logger = get_logger("scoring")


class LeadScorer:
    """Score leads based on multiple factors."""
    
    def __init__(self, config: dict):
        self.config = config
        self.scoring_rules = config["scoring"]["scoring_rules"]
        self.project_keywords = config["scoring"]["project_keywords"]
        self.hot_threshold = config["scoring"]["hot_threshold"]
        self.warm_threshold = config["scoring"]["warm_threshold"]
    
    def score_company(self, company_data: Dict) -> Dict:
        """Calculate lead score and priority for a company."""
        score = 0
        scoring_breakdown = []
        
        # Get text for analysis
        text = self._get_analysis_text(company_data)
        text_lower = text.lower()
        
        # Residential construction
        residential_keywords = ["residential", "apartment", "housing", "living", "жилой",
                               "բdelays", "բնակdelays", "բdelaysdelays"]
        if any(kw in text_lower for kw in residential_keywords):
            score += self.scoring_rules["residential_construction"]
            scoring_breakdown.append("residential_construction")
        
        # Commercial construction
        commercial_keywords = ["commercial", "office", "business", "retail", "shopping",
                              "商场", "ofis", "commerc"]
        if any(kw in text_lower for kw in commercial_keywords):
            score += self.scoring_rules["commercial_construction"]
            scoring_breakdown.append("commercial_construction")
        
        # Industrial construction
        industrial_keywords = ["industrial", "factory", "manufacturing", "plant",
                              "industr", "gammard"]
        if any(kw in text_lower for kw in industrial_keywords):
            score += self.scoring_rules["industrial_construction"]
            scoring_breakdown.append("industrial_construction")
        
        # Mentions parking
        parking_keywords = ["parking", "parking lot", "car park", "автостоянка",
                           "կdelays", "parking"]
        if any(kw in text_lower for kw in parking_keywords):
            score += self.scoring_rules["mentions_parking"]
            scoring_breakdown.append("mentions_parking")
        
        # Mentions garage
        garage_keywords = ["garage", "garages", "гараж", "garage"]
        if any(kw in text_lower for kw in garage_keywords):
            score += self.scoring_rules["mentions_garage"]
            scoring_breakdown.append("mentions_garage")
        
        # Mentions warehouse
        warehouse_keywords = ["warehouse", "storage", "depot", "склад", "պահdelays"]
        if any(kw in text_lower for kw in warehouse_keywords):
            score += self.scoring_rules["mentions_warehouse"]
            scoring_breakdown.append("mentions_warehouse")
        
        # Mentions logistics
        logistics_keywords = ["logistics", "distribution", "supply chain", "логистика"]
        if any(kw in text_lower for kw in logistics_keywords):
            score += self.scoring_rules["mentions_logistics"]
            scoring_breakdown.append("mentions_logistics")
        
        # More than 3 active projects
        project_count = company_data.get("project_count", 0)
        if project_count > 3:
            score += self.scoring_rules["more_than_3_projects"]
            scoring_breakdown.append("more_than_3_projects")
        
        # Has website
        if company_data.get("website"):
            score += self.scoring_rules["has_website"]
            scoring_breakdown.append("has_website")
        
        # Has email
        if company_data.get("email"):
            score += self.scoring_rules["has_email"]
            scoring_breakdown.append("has_email")
        
        # Has phone
        if company_data.get("phone"):
            score += self.scoring_rules["has_phone"]
            scoring_breakdown.append("has_phone")
        
        # Cap at 100
        score = min(score, 100)
        
        # Determine priority
        priority = self._determine_priority(score)
        
        company_data["lead_score"] = score
        company_data["lead_priority"] = priority
        company_data["_scoring_breakdown"] = scoring_breakdown
        
        logger.debug(
            f"Scored {company_data.get('company_name')}: {score} ({priority}) - "
            f"Breakdown: {', '.join(scoring_breakdown)}"
        )
        
        return company_data
    
    def _determine_priority(self, score: int) -> str:
        """Determine lead priority based on score."""
        if score >= self.hot_threshold:
            return "HOT"
        elif score >= self.warm_threshold:
            return "WARM"
        else:
            return "LOW"
    
    def _get_analysis_text(self, company_data: Dict) -> str:
        """Combine all text fields for analysis."""
        fields = [
            company_data.get("company_name", ""),
            company_data.get("company_description", ""),
            company_data.get("services", ""),
            company_data.get("project_names", ""),
            company_data.get("company_category", ""),
        ]
        
        return " ".join(str(f) for f in fields if f)
    
    def generate_intelligence_summary(self, company_data: Dict) -> str:
        """Generate a brief intelligence summary for the company."""
        name = company_data.get("company_name", "Unknown")
        city = company_data.get("city", "Unknown location")
        category = company_data.get("company_category", "construction")
        project_count = company_data.get("project_count", 0)
        score = company_data.get("lead_score", 0)
        
        # Determine focus area
        text = self._get_analysis_text(company_data).lower()
        
        focus_areas = []
        if any(kw in text for kw in ["residential", "apartment", "housing"]):
            focus_areas.append("residential")
        if any(kw in text for kw in ["commercial", "office", "business"]):
            focus_areas.append("commercial")
        if any(kw in text for kw in ["industrial", "factory"]):
            focus_areas.append("industrial")
        if any(kw in text for kw in ["parking", "garage"]):
            focus_areas.append("parking/garage")
        
        focus_str = " and ".join(focus_areas) if focus_areas else "general construction"
        
        summary = f"{name} is a {focus_str} company based in {city}."
        
        if project_count > 0:
            summary += f" Currently appears active on {project_count} project(s)."
        
        if score >= self.hot_threshold:
            summary += " Strong candidate for sectional garage doors, industrial doors, and loading dock systems."
        elif score >= self.warm_threshold:
            summary += " Good candidate for door and gate systems."
        else:
            summary += " May be interested in basic door systems."
        
        return summary
