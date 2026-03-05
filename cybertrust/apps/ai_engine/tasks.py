from __future__ import annotations

import logging
from typing import Optional, Dict, List

from celery import shared_task, chain, group
from django.db import transaction
from django.utils import timezone

from cybertrust.apps.ai_engine.services.analyze_control import (
    analyze_evidence_against_control,
    _extract_text,
)
from cybertrust.apps.evidence.models import Evidence, EvidenceControlLink
from cybertrust.apps.controls.models import Control, ControlScoreSnapshot
from cybertrust.apps.controls.services.scoring import (
    compute_control_score,
    compute_category_score,
    compute_overall_score,
)
from cybertrust.apps.organizations.models import Organization
from cybertrust.apps.audits.services import record_event

logger = logging.getLogger(__name__)


# ============================================================================
# CORE ANALYSIS TASKS
# ============================================================================


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    acks_late=True,
    reject_on_worker_lost=True,
)
def analyze_evidence_for_control(
    self,
    evidence_id: int,
    control_id: int,
    organization_id: Optional[int] = None,
) -> Dict[str, str]:
    """
    Async task to analyze evidence against a specific control.
    
    This is the main task that orchestrates:
    1. Evidence existence check
    2. Text extraction (if not already done)
    3. AI analysis against control requirements
    4. Score computation
    5. Audit event recording
    
    Args:
        evidence_id: ID of the evidence file to analyze
        control_id: ID of the control to analyze against
        organization_id: Optional org ID for audit trail
    
    Returns:
        Dict with task status and metadata
    
    Raises:
        Evidence.DoesNotExist: If evidence not found
        Control.DoesNotExist: If control not found
    """
    try:
        logger.info(
            f"Starting analysis: evidence={evidence_id}, control={control_id}, "
            f"attempt={self.request.retries + 1}/{self.max_retries}"
        )
        
        # Get evidence
        evidence = Evidence.objects.select_related('organization').get(id=evidence_id)
        control = Control.objects.get(id=control_id)
        organization_id = organization_id or evidence.organization_id
        
        # Call the orchestration service
        with transaction.atomic():
            result = analyze_evidence_against_control(evidence_id, control_id)
            
            # Record success event
            record_event(
                organization_id=organization_id,
                event_type='AI_ANALYSIS_COMPLETED',
                description=f'Analysis completed for evidence {evidence_id} against control {control_id}',
                metadata={
                    'evidence_id': evidence_id,
                    'control_id': control_id,
                    'task_id': self.request.id,
                    'timestamp': timezone.now().isoformat(),
                },
            )
        
        logger.info(f"Analysis completed successfully: evidence={evidence_id}, control={control_id}")
        return {
            'status': 'success',
            'evidence_id': evidence_id,
            'control_id': control_id,
            'message': 'Analysis completed successfully',
        }
        
    except Exception as exc:
        logger.error(
            f"Analysis failed: evidence={evidence_id}, control={control_id}, "
            f"error={str(exc)}, attempt={self.request.retries + 1}/{self.max_retries}",
            exc_info=True,
        )
        
        # Retry with exponential backoff: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    acks_late=True,
)
def extract_evidence_text(
    self,
    evidence_id: int,
    organization_id: Optional[int] = None,
) -> Dict[str, str]:
    """
    Async task to extract text from evidence file.
    
    Useful for:
    - Batch extraction of many files
    - Extracting without immediate analysis
    - Recovery from failed extractions
    
    Args:
        evidence_id: ID of evidence to extract
        organization_id: Optional org ID for audit
    
    Returns:
        Dict with extraction results and text length
    """
    try:
        logger.info(f"Starting text extraction: evidence={evidence_id}")
        
        evidence = Evidence.objects.select_related('organization').get(id=evidence_id)
        organization_id = organization_id or evidence.organization_id
        
        # Extract text
        _extract_text(evidence)
        evidence.refresh_from_db()
        
        # Record event
        record_event(
            organization_id=organization_id,
            event_type='TEXT_EXTRACTION_COMPLETED',
            description=f'Text extracted from evidence {evidence_id}',
            metadata={
                'evidence_id': evidence_id,
                'text_length': len(evidence.extracted_text or ''),
                'task_id': self.request.id,
            },
        )
        
        logger.info(
            f"Text extraction completed: evidence={evidence_id}, "
            f"text_length={len(evidence.extracted_text or '')}"
        )
        return {
            'status': 'success',
            'evidence_id': evidence_id,
            'text_length': len(evidence.extracted_text or ''),
        }
        
    except Exception as exc:
        logger.error(
            f"Text extraction failed: evidence={evidence_id}, error={str(exc)}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


# ============================================================================
# BATCH PROCESSING TASKS
# ============================================================================


@shared_task(acks_late=True)
def batch_analyze_evidence(evidence_ids: List[int], control_id: int) -> Dict:
    """
    Analyze multiple evidence files against a single control.
    
    Uses Celery group to analyze in parallel (respects worker concurrency).
    
    Args:
        evidence_ids: List of evidence IDs to analyze
        control_id: Control to analyze against
    
    Returns:
        Results of batch analysis
    """
    logger.info(
        f"Starting batch analysis: {len(evidence_ids)} evidence files "
        f"against control {control_id}"
    )
    
    # Create task group (parallel execution)
    job = group(
        analyze_evidence_for_control.s(eid, control_id)
        for eid in evidence_ids
    )
    
    result = job.apply_async()
    
    return {
        'status': 'queued',
        'batch_task_id': result.id,
        'evidence_count': len(evidence_ids),
        'control_id': control_id,
    }


@shared_task(acks_late=True)
def batch_analyze_control_full(control_id: int, organization_id: int) -> Dict:
    """
    Analyze all evidence for a specific control across the organization.
    
    Useful after:
    - Control definition updated
    - New batch of evidence uploaded
    - Need for full re-compliance assessment
    
    Args:
        control_id: Control to analyze
        organization_id: Organization context
    
    Returns:
        Batch job metadata
    """
    logger.info(
        f"Starting full control analysis: control={control_id}, org={organization_id}"
    )
    
    # Get all analyzed evidence from this org
    evidence_ids = Evidence.objects.filter(
        organization_id=organization_id,
        status=Evidence.STATUS_ANALYZED,
    ).values_list('id', flat=True)
    
    if not evidence_ids:
        logger.warning(
            f"No analyzed evidence found: control={control_id}, org={organization_id}"
        )
        return {'status': 'no_evidence', 'evidence_count': 0}
    
    return batch_analyze_evidence.delay(list(evidence_ids), control_id).asdict()


@shared_task(acks_late=True)
def extract_all_evidence_in_batch(organization_id: int) -> Dict:
    """
    Extract text from all non-extracted evidence.
    
    Useful for:
    - Initial setup
    - Recovery from extraction failures
    - Batch preprocessing before analysis
    
    Args:
        organization_id: Organization to process
    
    Returns:
        Batch job metadata
    """
    logger.info(f"Starting batch extraction: org={organization_id}")
    
    # Get evidence that needs extraction
    evidence_ids = Evidence.objects.filter(
        organization_id=organization_id,
        extracted_text__isnull=True,
    ).exclude(status=Evidence.STATUS_FAILED).values_list('id', flat=True)
    
    if not evidence_ids:
        logger.info(f"No evidence needs extraction: org={organization_id}")
        return {'status': 'complete', 'evidence_count': 0}
    
    # Create group for parallel extraction
    job = group(
        extract_evidence_text.s(eid, organization_id)
        for eid in evidence_ids
    )
    
    result = job.apply_async()
    
    return {
        'status': 'queued',
        'batch_task_id': result.id,
        'evidence_count': len(evidence_ids),
    }


# ============================================================================
# SCORING & AGGREGATION TASKS
# ============================================================================


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=2)
def compute_organization_scores(
    self,
    organization_id: int,
) -> Dict[str, any]:
    """
    Recompute all compliance scores for an organization.
    
    Should be called after:
    - New analysis results added
    - Scoring weights changed
    - Need for manual recalculation
    
    Args:
        organization_id: Organization to compute scores for
    
    Returns:
        Score summary
    """
    try:
        logger.info(f"Starting score computation: org={organization_id}")
        
        organization = Organization.objects.get(id=organization_id)
        
        # Compute overall score
        overall = compute_overall_score(organization)
        
        # Compute category scores
        categories = organization.categories.all()
        category_scores = {
            cat.id: compute_category_score(organization, cat)
            for cat in categories
        }
        
        logger.info(
            f"Score computation completed: org={organization_id}, "
            f"overall_score={overall}",
        )
        
        record_event(
            organization_id=organization_id,
            event_type='SCORES_RECOMPUTED',
            description='All compliance scores recomputed',
            metadata={
                'overall_score': overall,
                'category_count': len(category_scores),
                'task_id': self.request.id,
            },
        )
        
        return {
            'status': 'success',
            'overall_score': overall,
            'category_count': len(category_scores),
        }
        
    except Exception as exc:
        logger.error(
            f"Score computation failed: org={organization_id}, error={str(exc)}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# SCHEDULED/PERIODIC TASKS
# ============================================================================


@shared_task(acks_late=True)
def scheduled_extract_pending_evidence():
    """
    Scheduled task to extract text from pending evidence.
    
    Run every 6 hours via Celery Beat.
    
    Returns:
        Summary of extraction batches started
    """
    logger.info("Starting scheduled evidence extraction")
    
    # Get all organizations with pending evidence
    pending = Evidence.objects.filter(
        extracted_text__isnull=True,
    ).exclude(status=Evidence.STATUS_FAILED).values('organization_id').distinct()
    
    batches = []
    for org_data in pending:
        result = extract_all_evidence_in_batch.delay(org_data['organization_id'])
        batches.append(result.id)
    
    logger.info(f"Started {len(batches)} extraction batches")
    return {
        'status': 'started',
        'batch_count': len(batches),
        'batch_ids': batches,
    }


@shared_task(acks_late=True)
def scheduled_recompute_scores():
    """
    Scheduled task to recompute compliance scores.
    
    Run once daily via Celery Beat.
    Useful even without new analysis to catch scoring rule changes.
    
    Returns:
        Summary of organizations updated
    """
    logger.info("Starting scheduled score recomputation")
    
    organizations = Organization.objects.all()
    results = []
    
    for org in organizations:
        result = compute_organization_scores.delay(org.id)
        results.append(result.id)
    
    logger.info(f"Recomputed scores for {len(results)} organizations")
    return {
        'status': 'started',
        'organization_count': len(results),
        'task_ids': results,
    }


@shared_task(acks_late=True)
def cleanup_old_ai_results(days: int = 90) -> Dict[str, int]:
    """
    Optional: Delete old analysis results to save storage.
    
    Args:
        days: Delete results older than this many days
    
    Returns:
        Count of deleted records
    """
    from cybertrust.apps.ai_engine.models import AIAnalysisResult
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(days=days)
    count, _ = AIAnalysisResult.objects.filter(created_at__lt=cutoff).delete()
    
    logger.info(f"Deleted {count} old analysis results (older than {days} days)")
    return {'deleted_count': count, 'days': days}


# ============================================================================
# TASK CHAINING EXAMPLES
# ============================================================================


def run_complete_analysis_pipeline(evidence_id: int, control_ids: List[int]):
    """
    Example of task chaining: extract first, then analyze.
    
    Instead of running analyze_evidence_for_control which calls extract internally,
    you can separate the steps for more control.
    
    Args:
        evidence_id: Evidence to analyze
        control_ids: Controls to analyze against
    
    Returns:
        Chain task
    """
    # Chain: extract → analyze all controls in parallel
    extraction = extract_evidence_text.s(evidence_id)
    
    # After extraction, analyze against all controls in parallel
    analyses = group(
        analyze_evidence_for_control.s(evidence_id, cid)
        for cid in control_ids
    )
    
    # Use chain to sequence them
    pipeline = chain(extraction, analyses)
    return pipeline.apply_async()

# ============================================================================
# NCA COMPLIANCE AUDIT TASKS
# ============================================================================


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_nca_compliance_audit(
    self,
    evidence_id: int,
    org_id: int,
    user_id: int,
    control_codes: Optional[List[str]] = None,
) -> Dict[str, any]:
    """
    Async task to perform NCA compliance audit on evidence.
    
    Analyzes evidence text against all 114 NCA controls.
    Returns comprehensive JSON analysis per NCA auditor specification.
    
    Args:
        evidence_id: Evidence to audit
        org_id: Organization context
        user_id: User who triggered audit
        control_codes: Optional list of specific controls to analyze
    
    Returns:
        Dictionary with:
        - analysis[]: Array of control assessments
        - overall_assessment: Leadership summary
        - metadata: Audit details
    
    JSON Format:
        {
            "analysis": [
                {
                    "control_code": "NCA-ECC-1.1",
                    "status": "COMPLIANT | PARTIAL | NON_COMPLIANT | UNKNOWN",
                    "score": 0-100,
                    "confidence": 0-100,
                    "summary_ar": "Arabic summary",
                    "missing_points": ["point1", "point2"],
                    "recommendations": ["rec1", "rec2"],
                    "citations": [{"quote": "...", "page": 1}]
                }
            ],
            "overall_assessment": {
                "compliance_level": "HIGH | MEDIUM | LOW",
                "overall_score": 0-100,
                "key_gaps": ["gap1", "gap2"],
                "priority_actions": ["action1", "action2"]
            }
        }
    """
    try:
        # Fetch evidence
        try:
            evidence = Evidence.objects.get(id=evidence_id)
        except Evidence.DoesNotExist:
            logger.error(f"Evidence {evidence_id} not found")
            return {
                "error": "Evidence not found",
                "evidence_id": evidence_id
            }
        
        # Extract evidence text if not already extracted
        evidence_text = evidence.extracted_text
        if not evidence_text and evidence.file:
            logger.info(f"Extracting text from evidence {evidence_id}")
            evidence_text = _extract_text(evidence.file.path)
            evidence.extracted_text = evidence_text
            evidence.save(update_fields=['extracted_text'])
        
        if not evidence_text:
            logger.warning(f"No text available for evidence {evidence_id}")
            return {
                "error": "No extractable text in evidence",
                "evidence_id": evidence_id
            }
        
        # Initialize auditor and run analysis
        from cybertrust.apps.ai_engine.services.nca_compliance_auditor import (
            NCAComplianceAuditor,
        )
        
        auditor = NCAComplianceAuditor()
        analysis_result = auditor.analyze_evidence(
            evidence_text=evidence_text,
            control_codes=control_codes
        )
        
        # Log the audit event
        with transaction.atomic():
            org = Organization.objects.get(id=org_id)
            record_event(
                "COMPLIANCE_AUDIT_COMPLETED",
                user_id=user_id,
                organization=org,
                metadata={
                    "evidence_id": evidence_id,
                    "controls_analyzed": analysis_result["metadata"]["controls_analyzed"],
                    "overall_score": analysis_result["overall_assessment"]["overall_score"],
                    "compliance_level": analysis_result["overall_assessment"]["compliance_level"],
                }
            )
        
        logger.info(
            f"NCA audit completed for evidence {evidence_id}: "
            f"Score={analysis_result['overall_assessment']['overall_score']}"
        )
        
        return analysis_result
        
    except Exception as exc:
        logger.error(f"NCA audit task error: {str(exc)}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)