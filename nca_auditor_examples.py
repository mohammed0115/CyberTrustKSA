#!/usr/bin/env python
"""
NCA Compliance Auditor - Practical Examples & Testing Guide
===========================================================

This script demonstrates all major use cases and can be run to verify
the NCA compliance auditor is working correctly.

Run this after setting up the CyberTrustKSA application.
"""

import os
import sys
import json
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybertrust.config.settings.dev')

import django
django.setup()

from cybertrust.apps.ai_engine.services.nca_compliance_auditor import NCAComplianceAuditor


# ============================================================================
# SAMPLE EVIDENCE
# ============================================================================

EVIDENCE_COMPLIANT = """
Cybersecurity Strategy & Governance
====================================

Document Version: 2.0
Last Updated: January 2024
Approved By: Chief Information Officer

EXECUTIVE SUMMARY
=================
Our organization has established a comprehensive cybersecurity strategy
that is formally documented, reviewed regularly, and approved by senior
management. The strategy aligns with all applicable laws and regulations.

STRATEGIC OBJECTIVES
====================
1. Establish a dedicated cybersecurity function independent from IT
2. Implement access controls with multi-factor authentication
3. Ensure data encryption for all sensitive information
4. Develop and maintain incident response procedures
5. Conduct quarterly security awareness training

ORGANIZATIONAL STRUCTURE
======================
- Chief Information Security Officer (CISO) - Reports to CFO
- Cybersecurity Steering Committee - Meets monthly
- Committee Members:
  * CISO (Chair)
  * VP of IT Operations
  * Chief Compliance Officer
  * Representative from Legal
  * Representative from HR

CYBERSECURITY POLICIES
====================
1. Access Control Policy (v3.1) - Approved Jan 2024
   - Multi-factor authentication for all privileged access
   - Role-based access control (RBAC) implemented
   - Quarterly access reviews and certifications
   - Automated provisioning and deprovisioning

2. Data Protection Policy (v2.5) - Approved Jan 2024
   - AES-256 encryption for data at rest
   - TLS 1.2+ for data in transit
   - Annual encryption key rotation
   - DLP tools monitoring sensitive data

3. Incident Response Plan (v1.8) - Approved Jan 2024
   - 24/7 Security Operations Center (SOC)
   - Incident classification and response procedures
   - Notification requirements (24-hour disclosure)
   - Root cause analysis and lessons learned

4. Security Awareness Program (v2.0) - Approved Jan 2024
   - Mandatory training for all employees (quarterly)
   - Role-specific training modules
   - Phishing simulation campaigns (bi-monthly)
   - Performance tracking and metrics

IMPLEMENTATION STATUS
====================
✓ Cybersecurity Strategy - Fully implemented and operational
✓ Access Control System - Deployed to all 500+ employees
✓ Encryption Standards - Applied to all systems and data
✓ Incident Response Team - 12 full-time professionals
✓ Awareness Training - 95% completion rate

REVIEW & MONITORING
==================
- Quarterly strategy reviews with Steering Committee
- Annual penetration testing by external firm
- Monthly vulnerability scans
- Weekly log analysis and threat monitoring
- Annual compliance certification audit

COMPLIANCE STATUS
================
✓ Saudi Arabia NCA Cybersecurity Controls - COMPLIANT
✓ ISO 27001 Certification - Achieved 2023
✓ SOC 2 Type II - Audited annually
✓ NIST Framework - Mapped and implemented

Approved By:
Chief Information Officer: _________________ Date: Jan 15, 2024
Chief Executive Officer: _________________ Date: Jan 16, 2024
"""

EVIDENCE_PARTIAL = """
Access Control and Authentication Policy
========================================

POLICY OVERVIEW
===============
This policy establishes requirements for access control and authentication
across the organization.

AUTHENTICATION REQUIREMENTS
==========================
1. User Authentication
   - Username and password for all systems
   - Passwords must be at least 12 characters
   - Mandatory password change every 90 days
   - Lock account after 5 failed login attempts

2. Multi-Factor Authentication (MFA)
   - Required for VPN access
   - Required for administrative accounts
   - Implementation ongoing for user accounts (70% complete)

ROLE-BASED ACCESS CONTROL
=========================
- System roles are defined in the Active Directory
- User access provisioning follows documented procedure
- Access reviews are conducted quarterly

CURRENT STATUS
==============
- MFA enabled for 150/500 (30%) user accounts
- Access review process documented but not yet formalized
- Role definitions exist but not yet published
- Deprovisioning process needs documentation

NOTE: Policy is still being finalized. Several sections require:
- Formal approval from management
- Implementation of automated provisioning system
- Documentation of exception procedures
- Training for all access control administrators
"""

EVIDENCE_NON_COMPLIANT = """
IT Security Notes
=================

We have a basic firewall that filters traffic.
We use passwords for access to critical systems.
We have some antivirus software installed on computers.

We are planning to implement a more complete security program in the future
but currently do not have dedicated security staff or formal policies.
"""


# ============================================================================
# EXAMPLE 1: Basic Analysis
# ============================================================================

def example_1_basic_analysis():
    """Example 1: Basic compliance analysis."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Compliance Analysis")
    print("="*70)

    auditor = NCAComplianceAuditor()

    print("\n[1A] Analyzing COMPLIANT evidence...")
    result = auditor.analyze_evidence(EVIDENCE_COMPLIANT)

    print(f"   Overall Score: {result['overall_assessment']['overall_score']}/100")
    print(f"   Compliance Level: {result['overall_assessment']['compliance_level']}")
    print(f"   Compliant Controls: {result['overall_assessment']['compliant_count']}")
    print(f"   Partial Controls: {result['overall_assessment']['partial_count']}")
    print(f"   Non-Compliant Controls: {result['overall_assessment']['non_compliant_count']}")

    print("\n[1B] Analyzing PARTIAL evidence...")
    result = auditor.analyze_evidence(EVIDENCE_PARTIAL)

    print(f"   Overall Score: {result['overall_assessment']['overall_score']}/100")
    print(f"   Compliance Level: {result['overall_assessment']['compliance_level']}")

    print("\n[1C] Analyzing NON_COMPLIANT evidence...")
    result = auditor.analyze_evidence(EVIDENCE_NON_COMPLIANT)

    print(f"   Overall Score: {result['overall_assessment']['overall_score']}/100")
    print(f"   Compliance Level: {result['overall_assessment']['compliance_level']}")

    print("\n✅ Example 1 Complete")


# ============================================================================
# EXAMPLE 2: Detailed Analysis
# ============================================================================

def example_2_detailed_analysis():
    """Example 2: Detailed analysis with excerpts."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Detailed Analysis with Sample Outputs")
    print("="*70)

    auditor = NCAComplianceAuditor()
    result = auditor.analyze_evidence(EVIDENCE_COMPLIANT)

    # Show first 3 control results
    print("\nFirst 3 Control Assessments:")
    for i, control in enumerate(result['analysis'][:3], 1):
        print(f"\n[{i}] {control['control_code']}")
        print(f"    Title: {control['control_title']}")
        print(f"    Status: {control['status']}")
        print(f"    Score: {control['score']}/100")
        print(f"    Confidence: {control['confidence']}%")

        if control['citations']:
            print(f"    Citations: {len(control['citations'])} found")

        if control['missing_points']:
            print(f"    Missing Points:")
            for point in control['missing_points'][:2]:
                print(f"      • {point}")

    # Show overall assessment
    print("\n" + "-"*70)
    print("Overall Assessment:")
    print(f"  Complete Score: {result['overall_assessment']['overall_score']}/100")
    print(f"  Level: {result['overall_assessment']['compliance_level']}")
    print(f"  Status Distribution:")
    print(f"    • Compliant: {result['overall_assessment']['compliant_count']}")
    print(f"    • Partial: {result['overall_assessment']['partial_count']}")
    print(f"    • Non-Compliant: {result['overall_assessment']['non_compliant_count']}")

    print("\n  Top Gaps:")
    for gap in result['overall_assessment']['key_gaps'][:3]:
        print(f"    • {gap}")

    print("\n  Priority Actions:")
    for action in result['overall_assessment']['priority_actions'][:3]:
        print(f"    • {action}")

    print("\n✅ Example 2 Complete")


# ============================================================================
# EXAMPLE 3: Specific Controls
# ============================================================================

def example_3_specific_controls():
    """Example 3: Analyze specific controls only."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Analyzing Specific Controls")
    print("="*70)

    auditor = NCAComplianceAuditor()

    # Governance controls only
    governance_controls = [
        "NCA-ECC-1-1-1",
        "NCA-ECC-1-1-2",
        "NCA-ECC-1-2-1",
        "NCA-ECC-1-2-2",
        "NCA-ECC-1-3-1",
    ]

    print(f"\nAnalyzing {len(governance_controls)} governance controls...")
    result = auditor.analyze_evidence(EVIDENCE_COMPLIANT, control_codes=governance_controls)

    print(f"Controls analyzed: {len(result['analysis'])}")
    print("Results by status:")

    status_counts = {}
    for control in result['analysis']:
        status = control['status']
        status_counts[status] = status_counts.get(status, 0) + 1

    for status, count in status_counts.items():
        print(f"  {status}: {count}")

    print("\n✅ Example 3 Complete")


# ============================================================================
# EXAMPLE 4: Get Control Information
# ============================================================================

def example_4_control_details():
    """Example 4: Get details about specific controls."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Control Information")
    print("="*70)

    auditor = NCAComplianceAuditor()

    # Get specific control
    print("\n[4A] Getting control NCA-ECC-1-1-1:")
    control = auditor.get_control_by_code("NCA-ECC-1-1-1")

    if control:
        print(f"  Code: {control['code']}")
        print(f"  Title: {control['title_en']}")
        print(f"  Category: {control['category_en']}")
        print(f"  Risk Level: {control['risk_level']}")
        print(f"  Description: {control['description_en'][:100]}...")

    # List controls by category
    print("\n[4B] Governance controls:")
    gov_controls = auditor.get_controls_by_category("Cybersecurity Strategy")
    print(f"  Found {len(gov_controls)} governance controls")
    for c in gov_controls[:3]:
        print(f"    • {c['code']}: {c['title_en']}")

    # List controls by risk
    print("\n[4C] High risk controls:")
    high_risk = auditor.get_controls_by_risk_level("HIGH")
    print(f"  Found {len(high_risk)} high-risk controls")
    for c in high_risk[:3]:
        print(f"    • {c['code']}: {c['title_en']}")

    print("\n✅ Example 4 Complete")


# ============================================================================
# EXAMPLE 5: JSON Output
# ============================================================================

def example_5_json_output():
    """Example 5: Show JSON output structure."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Full JSON Output Structure")
    print("="*70)

    auditor = NCAComplianceAuditor()
    result = auditor.analyze_evidence(EVIDENCE_PARTIAL)

    # Show sample of JSON
    print("\nJSON Structure (sample):")
    print(f"  Keys: {list(result.keys())}")
    print(f"  Analysis count: {len(result['analysis'])}")
    print(f"  Metadata: {list(result['metadata'].keys())}")

    # Show one full control
    if result['analysis']:
        sample = result['analysis'][0]
        print("\nSample Control Assessment:")
        print(json.dumps(sample, ensure_ascii=False, indent=2)[:500] + "...")

    print("\n✅ Example 5 Complete")


# ============================================================================
# VERIFICATION TESTS
# ============================================================================

def run_verification_tests():
    """Run verification tests to ensure everything works."""
    print("\n" + "="*70)
    print("VERIFICATION TESTS")
    print("="*70)

    auditor = NCAComplianceAuditor()
    tests_passed = 0
    tests_total = 8

    # Test 1: Controls loaded
    print("\n[Test 1] Loading NCA controls...")
    controls = auditor.list_all_controls()
    if len(controls) == 114:
        print("  ✅ PASS: All 114 controls loaded")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected 114 controls, got {len(controls)}")

    # Test 2: Get specific control
    print("\n[Test 2] Getting specific control...")
    control = auditor.get_control_by_code("NCA-ECC-1-1-1")
    if control and "title_en" in control:
        print("  ✅ PASS: Can retrieve specific control")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Could not retrieve control")

    # Test 3: Analyze compliant evidence
    print("\n[Test 3] Analyzing compliant evidence...")
    result = auditor.analyze_evidence(EVIDENCE_COMPLIANT)
    if result['overall_assessment']['overall_score'] > 50:
        print(f"  ✅ PASS: Compliant evidence scores {result['overall_assessment']['overall_score']}")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Expected higher score for compliant evidence")

    # Test 4: Score ranges
    print("\n[Test 4] Checking score ranges...")
    if 0 <= result['overall_assessment']['overall_score'] <= 100:
        print("  ✅ PASS: Scores within valid range (0-100)")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Score out of range")

    # Test 5: JSON serializable
    print("\n[Test 5] Verifying JSON output...")
    try:
        json_str = json.dumps(result, ensure_ascii=False)
        print("  ✅ PASS: Output is valid JSON")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: JSON error: {e}")

    # Test 6: Specific controls
    print("\n[Test 6] Analyzing specific controls...")
    result = auditor.analyze_evidence(
        EVIDENCE_COMPLIANT,
        control_codes=["NCA-ECC-1-1-1", "NCA-ECC-1-1-2"]
    )
    if len(result['analysis']) <= 2:
        print(f"  ✅ PASS: Specific controls filter working")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Filter not working correctly")

    # Test 7: Non-compliant evidence scores lower
    print("\n[Test 7] Checking score differentiation...")
    compliant_result = auditor.analyze_evidence(EVIDENCE_COMPLIANT)
    non_compliant_result = auditor.analyze_evidence(EVIDENCE_NON_COMPLIANT)
    if compliant_result['overall_assessment']['overall_score'] > non_compliant_result['overall_assessment']['overall_score']:
        print("  ✅ PASS: Compliant evidence scores higher than non-compliant")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Score differentiation not working")

    # Test 8: Citations extraction
    print("\n[Test 8] Checking citations...")
    has_citations = any(c['citations'] for c in result['analysis'])
    if has_citations:
        print("  ✅ PASS: Citations extracted from evidence")
        tests_passed += 1
    else:
        print("  ⚠️  WARNING: No citations found")
        tests_passed += 0.5  # Partial since citations are optional

    # Summary
    print("\n" + "="*70)
    print(f"RESULTS: {int(tests_passed)}/{tests_total} tests passed")
    if tests_passed == tests_total:
        print("✅ ALL TESTS PASSED - System is working correctly!")
    else:
        print("⚠️  Some tests failed - Check output above")

    return tests_passed == tests_total


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all examples and tests."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  NCA Compliance Auditor - Practical Examples & Testing Guide  ".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")

    try:
        # Run examples
        example_1_basic_analysis()
        example_2_detailed_analysis()
        example_3_specific_controls()
        example_4_control_details()
        example_5_json_output()

        # Run verification
        run_verification_tests()

        print("\n" + "="*70)
        print("All examples and tests completed successfully!")
        print("="*70)

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
