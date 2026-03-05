from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from django.conf import settings

from cybertrust.apps.controls.models import Control

logger = logging.getLogger("ai_engine")

DEFAULT_MODEL = "gpt-4o-mini"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "nca_control_analysis.txt"


def build_unknown_result(reason: str) -> dict:
    return {
        "status": "UNKNOWN",
        "score": 0,
        "confidence": 0,
        "missing_points": [reason],
        "recommendations": ["Provide clearer evidence or additional documentation."],
        "citations": [],
        "summary_ar": "\u0627\u0644\u0645\u062d\u062a\u0648\u0649 \u063a\u064a\u0631 \u0643\u0627\u0641\u064d \u0644\u062a\u0642\u064a\u064a\u0645 \u0627\u0644\u0627\u0645\u062a\u062b\u0627\u0644.",
        "summary_en": "The evidence text is insufficient to assess compliance.",
    }


def _load_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise RuntimeError(f"Prompt file not found: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def _normalize_result(data: dict) -> dict:
    return {
        "status": data.get("status", "UNKNOWN"),
        "score": int(data.get("score", 0)),
        "confidence": int(data.get("confidence", 0)),
        "missing_points": data.get("missing_points") or [],
        "recommendations": data.get("recommendations") or [],
        "citations": data.get("citations") or [],
        "summary_ar": "\u0627\u0644\u0645\u062d\u062a\u0648\u0649 \u063a\u064a\u0631 \u0643\u0627\u0641\u064d \u0644\u062a\u0642\u064a\u064a\u0645 \u0627\u0644\u0627\u0645\u062a\u062b\u0627\u0644.",
        "summary_en": data.get("summary_en") or "",
    }


def analyze_control_text(evidence_text: str, control: Control, model_name: str | None = None) -> dict:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("openai package is required for AI analysis") from exc

    prompt = _load_prompt()
    model = model_name or getattr(settings, "OPENAI_MODEL", DEFAULT_MODEL)
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)

    messages = [
        {"role": "system", "content": prompt.strip()},
        {
            "role": "user",
            "content": (
                f"CONTROL_CODE: {control.code}\n"
                f"TITLE_AR: {control.title_ar}\n"
                f"TITLE_EN: {control.title_en}\n"
                f"DESCRIPTION_AR: {control.description_ar or ''}\n"
                f"DESCRIPTION_EN: {control.description_en or ''}\n"
                f"REQUIRED_EVIDENCE: {control.required_evidence}\n\n"
                f"EVIDENCE_TEXT:\n{evidence_text}\n"
            ),
        },
    ]

    last_error = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = response.choices[0].message.content or "{}"
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    data = json.loads(content[start : end + 1])
                else:
                    raise
            normalized = _normalize_result(data)
            normalized["model_name"] = model
            return normalized
        except Exception as exc:  # pragma: no cover
            last_error = exc
            logger.exception("OpenAI call failed (attempt %s)", attempt + 1)
            time.sleep(2 ** attempt)

    raise RuntimeError(f"OpenAI analysis failed: {last_error}")
