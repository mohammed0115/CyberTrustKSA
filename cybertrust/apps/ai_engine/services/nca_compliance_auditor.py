"""
NCA Compliance Auditor Service
==============================
Analyzes evidence text against all 114 NCA controls.
Implements professional cybersecurity compliance audit methodology.

Author: CyberTrust AI Engine
Version: 1.0
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from django.core.cache import cache
from django.db import models

logger = logging.getLogger(__name__)


class NCAComplianceAuditor:
    """
    Professional NCA compliance auditor for analyzing evidence against controls.
    """

    # Compliance thresholds
    COMPLIANCE_THRESHOLDS = {
        "COMPLIANT": 100,
        "PARTIAL": (40, 80),
        "NON_COMPLIANT": (0, 40),
        "UNKNOWN": 20,
    }

    RISK_LEVEL_WEIGHTS = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    COMPLIANCE_KEYWORDS = {
        # Control categories
        "governance": ["governance", "strategy", "policy", "framework", "plan"],
        "management": ["manage", "responsibility", "role", "procedure", "process"],
        "organizational": ["organization", "department", "division", "function"],
        "implementation": ["implement", "deploy", "establish", "configure"],
        "monitoring": ["monitor", "audit", "assess", "review", "track"],
        "incident": ["incident", "breach", "vulnerability", "threat", "attack"],
        "access_control": [
            "access",
            "authentication",
            "authorization",
            "permission",
            "role",
        ],
        "encryption": ["encrypt", "secure", "cipher", "hash", "ssl", "tls"],
        "network": ["network", "firewall", "segmentation", "vpn", "proxy"],
        "data_protection": ["data", "privacy", "confidential", "backup", "recovery"],
        "awareness": ["awareness", "training", "education", "knowledge"],
    }

    def __init__(self):
        """Initialize the auditor and load NCA controls."""
        self.controls = self._load_nca_controls()
        self.control_map = {c["code"]: c for c in self.controls}
        self.analysis_timestamp = datetime.now().isoformat()

    def _load_nca_controls(self) -> List[Dict[str, Any]]:
        """
        Load NCA controls from seed JSON file.

        Returns:
            List of control dictionaries
        """
        cache_key = "nca_controls_cache"
        cached = cache.get(cache_key)
        if cached:
            return cached

        json_path = Path(__file__).parent.parent / "data" / "nca_controls_seed.json"

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                controls = json.load(f)
            cache.set(cache_key, controls, timeout=86400)  # Cache 24 hours
            logger.info(f"Loaded {len(controls)} NCA controls from {json_path}")
            return controls
        except FileNotFoundError:
            logger.error(f"NCA controls JSON not found at {json_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing NCA controls JSON: {e}")
            return []

    def analyze_evidence(
        self, evidence_text: str, control_codes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze evidence text against NCA controls.

        Args:
            evidence_text: Full text of the evidence document
            control_codes: Optional list of specific controls to analyze.
                          If None, analyzes all controls.

        Returns:
            Dictionary with compliance analysis results
        """
        if not evidence_text or not evidence_text.strip():
            return self._empty_analysis("Evidence text is empty")

        # Normalize text
        evidence_lower = evidence_text.lower()
        evidence_words = set(evidence_lower.split())

        # Select controls to analyze
        controls_to_analyze = self.controls
        if control_codes:
            controls_to_analyze = [
                c for c in self.controls if c["code"] in control_codes
            ]

        # Analyze each control
        analysis_results = []
        for control in controls_to_analyze:
            result = self._analyze_control(
                control, evidence_text, evidence_lower, evidence_words
            )
            analysis_results.append(result)

        # Calculate overall assessment
        overall = self._calculate_overall_assessment(analysis_results)

        return {
            "analysis": analysis_results,
            "overall_assessment": overall,
            "metadata": {
                "analysis_timestamp": self.analysis_timestamp,
                "evidence_length": len(evidence_text),
                "controls_analyzed": len(analysis_results),
                "auditor_version": "1.0",
            },
        }

    def _analyze_control(
        self, control: Dict, evidence_text: str, evidence_lower: str, evidence_words: set
    ) -> Dict[str, Any]:
        """
        Analyze a single control against evidence.

        Args:
            control: Control definition
            evidence_text: Original evidence text
            evidence_lower: Lowercase evidence text
            evidence_words: Set of words from evidence

        Returns:
            Analysis result for the control
        """
        code = control.get("code", "")
        title = control.get("title_en", "")
        description = control.get("description_en", "")
        risk_level = control.get("risk_level", "MEDIUM")

        # Calculate compliance score
        score, confidence = self._calculate_compliance_score(
            title, description, evidence_lower, evidence_words
        )

        # Determine status
        status = self._determine_status(score)

        # Extract citations
        citations = self._extract_citations(evidence_text, title, description)

        # Identify missing points
        missing_points = self._identify_missing_points(
            title, description, evidence_lower
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            status, title, description, missing_points
        )

        return {
            "control_code": code,
            "control_title": title,
            "control_risk_level": risk_level,
            "status": status,
            "score": int(score),
            "confidence": int(confidence),
            "summary_ar": self._generate_arabic_summary(status, score, title),
            "summary_en": self._generate_english_summary(status, score, title),
            "missing_points": missing_points[:5],  # Limit to 5
            "recommendations": recommendations[:5],  # Limit to 5
            "citations": citations,
        }

    def _calculate_compliance_score(
        self, title: str, description: str, evidence_lower: str, evidence_words: set
    ) -> tuple[float, float]:
        """
        Calculate compliance score using keyword matching and relevance analysis.

        Returns:
            Tuple of (score, confidence)
        """
        # Extract key terms from control
        control_terms = self._extract_key_terms(title + " " + description)

        if not control_terms:
            return 20, 30  # Unknown status

        # Calculate keyword match percentage
        matched_terms = sum(1 for term in control_terms if term in evidence_words)
        match_percentage = (
            (matched_terms / len(control_terms)) * 100
            if control_terms
            else 0
        )

        # Check for category context
        category_matches = self._check_category_matches(
            control_terms, evidence_lower
        )

        # Calculate detail level
        detail_score = self._calculate_detail_score(
            evidence_lower, control_terms
        )

        # Combine scores
        keyword_score = match_percentage * 0.4  # 40% - keyword match
        category_score = category_matches * 0.3  # 30% - category context
        detail_score_weighted = detail_score * 0.3  # 30% - detail level

        final_score = keyword_score + category_score + detail_score_weighted

        # Calculate confidence based on evidence density
        confidence = min(
            100,
            (len(evidence_words) / 100) * 50 + min(match_percentage, 100) * 0.5,
        )

        return final_score, confidence

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract important terms from control title/description."""
        # Remove common words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "is",
            "are",
            "am",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
        }

        words = text.lower().split()
        terms = [
            w.strip(".,;:-") for w in words if w.strip(".,;:-") not in stop_words
        ]
        return list(set(terms))[:15]  # Return unique, limit to 15

    def _check_category_matches(
        self, control_terms: List[str], evidence_lower: str
    ) -> float:
        """Check if document contains relevant category context."""
        score = 0
        for category, keywords in self.COMPLIANCE_KEYWORDS.items():
            matched = sum(1 for kw in keywords if kw in evidence_lower)
            if matched > 0:
                score += min(matched, 2)  # Cap at 2 per category

        return min(100, (score / 15) * 100)  # Normalize to 100

    def _calculate_detail_score(
        self, evidence_lower: str, control_terms: List[str]
    ) -> float:
        """Calculate how detailed the evidence is."""
        # Check for specific procedures, dates, names, etc.
        detail_indicators = [
            "procedure",
            "process",
            "document",
            "policy",
            "approved",
            "implemented",
            "date",
            "version",
            "review",
            "audit",
        ]

        found = sum(
            1 for indicator in detail_indicators if indicator in evidence_lower
        )
        return min(100, (found / len(detail_indicators)) * 100)

    def _determine_status(self, score: float) -> str:
        """Determine compliance status based on score."""
        if score >= 90:
            return "COMPLIANT"
        elif 40 <= score < 90:
            return "PARTIAL"
        elif 20 <= score < 40:
            return "NON_COMPLIANT"
        else:
            return "UNKNOWN"

    def _extract_citations(
        self, evidence_text: str, title: str, description: str
    ) -> List[Dict[str, Any]]:
        """
        Extract relevant quotes from evidence that support compliance.

        Returns:
            List of citations with quote and page/section
        """
        citations = []

        # Extract sentences that mention key terms from control
        key_terms = self._extract_key_terms(title + " " + description)
        sentences = evidence_text.split(".")

        relevant_sentences = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            matched_terms = sum(1 for term in key_terms if term in sentence_lower)
            if matched_terms >= 2:  # At least 2 key terms
                relevant_sentences.append(sentence.strip())

        # Format citations (limit to 5, max 25 words each)
        for i, sentence in enumerate(relevant_sentences[:5]):
            words = sentence.split()[:25]  # Limit to 25 words
            quote = " ".join(words)
            if len(quote) > 20:  # Only include substantial quotes
                citations.append(
                    {
                        "quote": quote,
                        "page": i + 1,
                    }
                )

        return citations

    def _identify_missing_points(
        self, title: str, description: str, evidence_lower: str
    ) -> List[str]:
        """Identify points not covered in the evidence."""
        missing = []

        # Common requirements for controls
        required_elements = {
            "documentation": "Written documentation or policy",
            "approval": "Management review and approval",
            "implementation": "Evidence of implementation",
            "review": "Periodic review or audit results",
            "responsibility": "Defined roles and responsibilities",
        }

        for element, description_text in required_elements.items():
            if element not in evidence_lower:
                missing.append(description_text)

        return missing[:5]

    def _generate_recommendations(
        self,
        status: str,
        title: str,
        description: str,
        missing_points: List[str],
    ) -> List[str]:
        """Generate recommendations based on compliance status."""
        recommendations = []

        if status == "COMPLIANT":
            recommendations.append("Maintain current documentation and procedures")
            recommendations.append("Conduct annual review to ensure continued compliance")
        elif status == "PARTIAL":
            if missing_points:
                recommendations.append(
                    f"Document the following: {missing_points[0]}"
                )
            recommendations.append(
                "Enhance evidence with additional implementation details"
            )
            recommendations.append("Schedule a compliance review meeting")
        elif status == "NON_COMPLIANT":
            recommendations.append(
                f"Immediately establish: {title}"
            )
            recommendations.append(
                "Develop and document procedures as per control requirements"
            )
            recommendations.append("Allocate resources for implementation")
            recommendations.append("Create an action plan with target dates")
        else:  # UNKNOWN
            recommendations.append(
                "Provide more comprehensive evidence for assessment"
            )
            recommendations.append("Include specific policies and procedures")

        return recommendations[:5]

    def _generate_arabic_summary(
        self, status: str, score: float, title: str
    ) -> str:
        """Generate Arabic summary of assessment."""
        status_ar = {
            "COMPLIANT": "متوافق كاملاً",
            "PARTIAL": "متوافق جزئياً",
            "NON_COMPLIANT": "غير متوافق",
            "UNKNOWN": "غير محدد",
        }.get(status, "غير معروف")

        return f"{status_ar} - {title} ({int(score)}/100)"

    def _generate_english_summary(
        self, status: str, score: float, title: str
    ) -> str:
        """Generate English summary of assessment."""
        return f"{status} - {title} (Score: {int(score)}/100)"

    def _calculate_overall_assessment(
        self, analysis_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate overall compliance assessment."""
        if not analysis_results:
            return {
                "compliance_level": "UNKNOWN",
                "overall_score": 0,
                "key_gaps": [],
                "priority_actions": [],
            }

        scores = [r["score"] for r in analysis_results]
        statuses = [r["status"] for r in analysis_results]

        overall_score = sum(scores) / len(scores) if scores else 0

        # Determine compliance level
        if overall_score >= 85:
            compliance_level = "HIGH"
        elif overall_score >= 50:
            compliance_level = "MEDIUM"
        else:
            compliance_level = "LOW"

        # Get low-scoring controls (gaps)
        low_scoring = sorted(
            [r for r in analysis_results if r["score"] < 50],
            key=lambda x: x["score"],
        )
        key_gaps = [r["control_code"] + ": " + r["control_title"] for r in low_scoring[:5]]

        # Get non-compliant and partial controls for priority actions
        non_compliant = [
            r for r in analysis_results if r["status"] in ["NON_COMPLIANT"]
        ]
        partial = [r for r in analysis_results if r["status"] in ["PARTIAL"]]

        priority_controls = non_compliant[:3] + partial[:2]
        priority_actions = [
            f"Address {r['control_code']}: {r['recommendations'][0]}"
            for r in priority_controls
            if r.get("recommendations")
        ]

        return {
            "compliance_level": compliance_level,
            "overall_score": int(overall_score),
            "compliant_count": statuses.count("COMPLIANT"),
            "partial_count": statuses.count("PARTIAL"),
            "non_compliant_count": statuses.count("NON_COMPLIANT"),
            "unknown_count": statuses.count("UNKNOWN"),
            "key_gaps": key_gaps,
            "priority_actions": priority_actions[:5],
        }

    def _empty_analysis(self, reason: str) -> Dict[str, Any]:
        """Return empty analysis result."""
        return {
            "analysis": [],
            "overall_assessment": {
                "compliance_level": "UNKNOWN",
                "overall_score": 0,
                "key_gaps": [reason],
                "priority_actions": ["Provide evidence text for analysis"],
            },
            "metadata": {
                "analysis_timestamp": self.analysis_timestamp,
                "error": reason,
            },
        }

    def get_control_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get a specific control by its code."""
        return self.control_map.get(code)

    def list_all_controls(self) -> List[Dict[str, Any]]:
        """Get all available NCA controls."""
        return self.controls

    def get_controls_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get controls by category."""
        return [c for c in self.controls if category in c.get("category_en", "")]

    def get_controls_by_risk_level(self, risk_level: str) -> List[Dict[str, Any]]:
        """Get controls by risk level."""
        return [c for c in self.controls if c.get("risk_level") == risk_level]
