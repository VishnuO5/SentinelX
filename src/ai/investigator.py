"""
src/ai/investigator.py
========================
The AI Investigator: turns a raw evidence bundle (case + account + signals
+ comments + reports + campaign) into a structured Summary + Evidence +
Recommendation, the way an analyst would write up a case conclusion.

Two modes:
  - LLM mode (Groq, if GROQ_API_KEY is set): the evidence bundle is
    formatted into a prompt and sent to Groq's Llama model, which returns
    the writeup. This is the "design and refine LLM prompts" JD line.
  - Fallback mode (no API key): a deterministic, rule-based writeup built
    directly from the same evidence -- every number in it is real (comes
    from the database), it's just template-assembled instead of
    LLM-generated. This means the module still works end-to-end (and is
    fully testable) with zero external dependencies or secrets.

Either way, the RETURNED SHAPE is identical, so the page never needs to
know which mode produced it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _resolve_groq_api_key(explicit_key: str | None) -> str | None:
    """Checks, in order: an explicitly passed key, Streamlit Cloud's
    st.secrets, then a plain OS environment variable.

    FIX: this used to only check os.environ.get("GROQ_API_KEY"). That
    works for local development (a shell env var or .env loader), but on
    Streamlit Cloud, secrets added through the app's Settings -> Secrets
    panel are exposed via st.secrets, NOT mirrored into os.environ. So a
    correctly-configured key on Streamlit Cloud was silently invisible to
    this code, and the app would show fallback mode even with a real key
    set -- looking like a bug rather than a missing code path.
    """
    if explicit_key:
        return explicit_key

    try:
        import streamlit as st
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        # No secrets.toml locally, not running under Streamlit, or
        # secrets access otherwise unavailable -- fall through to env var.
        pass

    return os.environ.get("GROQ_API_KEY")


PROMPT_TEMPLATE = """You are a Trust & Safety investigator writing up a case conclusion for a fellow analyst. Be concise, evidence-driven, and specific -- cite the actual numbers given below. Do not invent facts not present in the evidence.

CASE
  case_id: {case_id}
  case_type: {case_type}
  priority: {priority}
  status: {status}
  opened_at: {opened_at}

ACCOUNT
  account_id: {account_id}
  display_name: {display_name}
  status: {account_status}
  created_at: {created_at}
  device_id: {device_id}
  ip_region: {ip_region}

CAMPAIGN LINK
{campaign_block}

SIGNAL ENGINE SCORES (0.0-1.0, higher = more suspicious)
  account_age_signal: {account_age_signal}
  report_volume_signal: {report_volume_signal}
  device_reuse_signal: {device_reuse_signal}
  ip_region_signal: {ip_region_signal}
  toxicity_signal: {toxicity_signal}
  composite_risk_score: {composite_risk_score}

REPORT REASONS FILED AGAINST THIS ACCOUNT
{report_block}

TOP COMMENTS BY TOXICITY SCORE (most suspicious first)
{comment_block}

Respond in exactly this format:
SUMMARY: <2-3 sentence summary of what this account did and why it's under investigation>
EVIDENCE: <3-5 bullet points, each citing a specific number or fact from above>
RECOMMENDATION: <one clear recommended action: e.g. "Suspend account", "Escalate to senior review", "Monitor, insufficient evidence to act", "Close, false positive">
CONFIDENCE: <High, Medium, or Low, based on how strong and consistent the evidence is>
"""


def _format_campaign_block(campaign: dict | None) -> str:
    if not campaign:
        return "  Not linked to any known campaign (standalone account)."
    return (
        f"  campaign_id: {campaign['campaign_id']}\n"
        f"  campaign_type: {campaign['campaign_type']}\n"
        f"  velocity_score: {campaign['velocity_score']}\n"
        f"  similarity_score: {campaign['similarity_score']}\n"
        f"  network_density: {campaign['network_density']}\n"
        f"  campaign_status: {campaign['status']}"
    )


def _format_report_block(reports: list) -> str:
    if not reports:
        return "  No reports filed against this account."
    return "\n".join(f"  {r['report_reason']}: {r['count']}" for r in reports)


def _format_comment_block(comments: list) -> str:
    if not comments:
        return "  No comments on record for this account."
    lines = []
    for c in comments[:5]:
        text = (c["text"] or "")[:160].replace("\n", " ")
        lines.append(f"  [{c['toxicity_label']}, score={c['toxicity_score']}] \"{text}\"")
    return "\n".join(lines)


def build_prompt(bundle: dict) -> str:
    case = bundle["case"]
    account = bundle["account"]
    signals = bundle.get("signals") or {}

    return PROMPT_TEMPLATE.format(
        case_id=case.get("case_id"), case_type=case.get("case_type"),
        priority=case.get("priority"), status=case.get("status"),
        opened_at=case.get("opened_at"),
        account_id=account.get("account_id"), display_name=account.get("display_name"),
        account_status=account.get("status"), created_at=account.get("created_at"),
        device_id=account.get("device_id"), ip_region=account.get("ip_region"),
        campaign_block=_format_campaign_block(bundle.get("campaign")),
        account_age_signal=signals.get("account_age_signal", "n/a"),
        report_volume_signal=signals.get("report_volume_signal", "n/a"),
        device_reuse_signal=signals.get("device_reuse_signal", "n/a"),
        ip_region_signal=signals.get("ip_region_signal", "n/a"),
        toxicity_signal=signals.get("toxicity_signal", "n/a"),
        composite_risk_score=signals.get("composite_risk_score", "n/a"),
        report_block=_format_report_block(bundle.get("reports") or []),
        comment_block=_format_comment_block(bundle.get("comments") or []),
    )


def _parse_llm_response(text: str) -> dict:
    """Parses the SUMMARY/EVIDENCE/RECOMMENDATION/CONFIDENCE format back
    into a dict. Falls back gracefully if the model didn't follow the
    format exactly."""
    sections = {"summary": "", "evidence": "", "recommendation": "", "confidence": ""}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("SUMMARY:"):
            current = "summary"
            sections[current] = stripped.split(":", 1)[1].strip()
        elif upper.startswith("EVIDENCE:"):
            current = "evidence"
            sections[current] = stripped.split(":", 1)[1].strip()
        elif upper.startswith("RECOMMENDATION:"):
            current = "recommendation"
            sections[current] = stripped.split(":", 1)[1].strip()
        elif upper.startswith("CONFIDENCE:"):
            current = "confidence"
            sections[current] = stripped.split(":", 1)[1].strip()
        elif current:
            sections[current] += ("\n" + stripped if stripped else "")
    return sections


def _rule_based_fallback(bundle: dict) -> dict:
    """No API key available -- build the same structured output directly
    from the evidence bundle instead of calling an LLM. Every fact here
    is real (pulled straight from the database), just assembled by
    template rather than by a model."""
    case = bundle["case"]
    account = bundle["account"]
    signals = bundle.get("signals") or {}
    campaign = bundle.get("campaign")
    reports = bundle.get("reports") or []
    comments = bundle.get("comments") or []

    risk = signals.get("composite_risk_score", 0.0) or 0.0
    total_reports = sum(r["count"] for r in reports)
    toxic_comments = [c for c in comments if c.get("toxicity_label") not in (None, "clean")]

    campaign_phrase = (
        f"linked to campaign {campaign['campaign_id']} ({campaign['campaign_type']}, "
        f"similarity {campaign['similarity_score']:.2f})"
        if campaign else "not linked to any known coordinated campaign"
    )

    summary = (
        f"Account {account.get('account_id')} was flagged for a {case.get('case_type')} case "
        f"(priority: {case.get('priority')}). It is {campaign_phrase}. "
        f"Composite risk score is {risk:.3f}, driven primarily by "
        f"{_top_signal_name(signals)}."
    )

    evidence_lines = []
    evidence_lines.append(f"Composite risk score: {risk:.3f} (see Unified Signal Engine breakdown).")
    if total_reports:
        top_reason = reports[0]["report_reason"]
        evidence_lines.append(f"{total_reports} total reports filed, most commonly for '{top_reason}'.")
    else:
        evidence_lines.append("No reports on file for this account.")
    if toxic_comments:
        evidence_lines.append(
            f"{len(toxic_comments)} of {len(comments)} sampled comments flagged toxic "
            f"(highest score: {comments[0]['toxicity_score']:.3f})."
        )
    if campaign:
        evidence_lines.append(
            f"Campaign {campaign['campaign_id']} shows network_density={campaign['network_density']:.2f} "
            f"and velocity_score={campaign['velocity_score']:.2f}."
        )
    evidence_lines.append(f"Account age signal: {signals.get('account_age_signal', 'n/a')}, "
                           f"device reuse signal: {signals.get('device_reuse_signal', 'n/a')}.")

    if risk >= 0.55:
        recommendation = "Suspend account and close linked campaign cluster for review."
        confidence = "High"
    elif risk >= 0.4:
        recommendation = "Escalate to senior analyst for manual review."
        confidence = "Medium"
    elif total_reports == 0 and not campaign:
        recommendation = "Close, insufficient evidence to act."
        confidence = "Medium"
    else:
        recommendation = "Monitor account; re-evaluate if new reports arrive."
        confidence = "Low"

    return {
        "summary": summary,
        "evidence": "\n".join(f"- {line}" for line in evidence_lines),
        "recommendation": recommendation,
        "confidence": confidence,
        "mode": "fallback",
    }


def _top_signal_name(signals: dict) -> str:
    labels = {
        "account_age_signal": "account age",
        "report_volume_signal": "report volume",
        "device_reuse_signal": "device reuse",
        "ip_region_signal": "IP region clustering",
        "toxicity_signal": "comment toxicity",
    }
    if not signals:
        return "insufficient signal data"
    best_key = max(labels, key=lambda k: signals.get(k) or 0.0)
    return labels[best_key]


class AIInvestigator:

    def __init__(self, api_key: str | None = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = _resolve_groq_api_key(api_key)
        self.model = model

    def investigate(self, bundle: dict) -> dict:
        if not bundle.get("case"):
            return {"error": "No case data provided."}

        if self.api_key:
            try:
                return self._investigate_via_groq(bundle)
            except Exception as exc:  # network/API failure -- degrade gracefully
                result = _rule_based_fallback(bundle)
                result["mode"] = "fallback"
                result["fallback_reason"] = f"Groq call failed: {exc}"
                return result

        return _rule_based_fallback(bundle)

    def _investigate_via_groq(self, bundle: dict) -> dict:
        from groq import Groq  # imported lazily so the module works without the package

        client = Groq(api_key=self.api_key)
        prompt = build_prompt(bundle)

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600,
        )
        text = response.choices[0].message.content
        parsed = _parse_llm_response(text)
        parsed["mode"] = "llm"
        return parsed