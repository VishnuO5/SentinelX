"""
src/ai/reasoning_engine.py
=============================
The AI Investigator (investigator.py) does one-shot prompting. This
engine produces an explicit multi-step reasoning TRACE instead --
Evidence Gathering -> Pattern Analysis -> Risk Correlation -> Verdict --
so the analyst can see how the conclusion was reached, not just what it
was.

Same two-mode design as investigator.py (LLM via Groq if GROQ_API_KEY is
set, otherwise a real fallback built directly from the evidence bundle).
Standalone -- not wired into investigator.py's existing call path, so
the already-tested AI Investigator page is unaffected.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

STEP_NAMES = ["Evidence Gathering", "Pattern Analysis", "Risk Correlation", "Verdict"]

REASONING_PROMPT_TEMPLATE = """You are a Trust & Safety investigator. Think through this case in four explicit steps, in order. Be concise and specific -- cite the real numbers given below, do not invent facts.

CASE
  case_id: {case_id}
  case_type: {case_type}
  priority: {priority}
  status: {status}

ACCOUNT
  account_id: {account_id}
  risk_score: {risk_score}

SIGNALS
  account_age_signal: {account_age_signal}
  report_volume_signal: {report_volume_signal}
  device_reuse_signal: {device_reuse_signal}
  ip_region_signal: {ip_region_signal}
  toxicity_signal: {toxicity_signal}

CAMPAIGN
  {campaign_phrase}

REPORTS
  total: {total_reports}, most common reason: {top_reason}

COMMENTS
  {toxic_comment_count} of {total_comment_count} sampled comments flagged toxic

Respond with exactly four sections, each starting with its label on its own line:

EVIDENCE GATHERING:
<one or two sentences listing what evidence exists>

PATTERN ANALYSIS:
<one or two sentences on what pattern this evidence suggests>

RISK CORRELATION:
<one or two sentences on how the signals and campaign context correlate to raise or lower risk>

VERDICT:
<one sentence final call: what should happen to this case>
"""


def _top_signal_name(signals: dict) -> str:
    labels = {
        "account_age_signal": "account age",
        "report_volume_signal": "report volume",
        "device_reuse_signal": "device reuse",
        "ip_region_signal": "IP region clustering",
        "toxicity_signal": "comment toxicity",
    }
    # Maps each signal_scores column name to its config.SIGNAL_WEIGHTS key.
    weight_keys = {
        "account_age_signal": "account_age",
        "report_volume_signal": "report_volume",
        "device_reuse_signal": "device_reuse",
        "ip_region_signal": "ip_region",
        "toxicity_signal": "toxicity",
    }
    if not signals:
        return "insufficient signal data"

    # FIX: this used to pick the signal with the highest RAW value
    # (signals.get(k)), which can mislabel the explanation -- e.g. a
    # 0.9984 account-age signal (weight 0.15) would get called
    # "dominant" over a 0.75 device-reuse signal (weight 0.25), even
    # though device reuse actually contributes more to the composite
    # score (0.75 * 0.25 = 0.1875 vs 0.9984 * 0.15 = 0.150). Now it
    # picks by WEIGHTED CONTRIBUTION, which is what actually drives the
    # composite score -- so the explanation matches the math.
    best_key = max(
        labels,
        key=lambda k: (signals.get(k) or 0.0) * config.SIGNAL_WEIGHTS[weight_keys[k]],
    )
    return labels[best_key]


def _rule_based_trace(bundle: dict) -> dict:
    case = bundle["case"]
    account = bundle["account"]
    signals = bundle.get("signals") or {}
    campaign = bundle.get("campaign")
    reports = bundle.get("reports") or []
    comments = bundle.get("comments") or []

    risk = signals.get("composite_risk_score", 0.0) or 0.0
    total_reports = sum(r["count"] for r in reports)
    toxic_comments = [c for c in comments if c.get("toxicity_label") not in (None, "clean")]
    top_signal = _top_signal_name(signals)

    campaign_phrase = (
        f"linked to campaign {campaign['campaign_id']} ({campaign['campaign_type']}), "
        f"network density {campaign['network_density']:.2f}, velocity {campaign['velocity_score']:.2f}"
        if campaign else "no known campaign link"
    )

    step1 = (
        f"Account {account.get('account_id')} has {total_reports} report(s) filed"
        + (f", most commonly for '{reports[0]['report_reason']}'" if reports else "")
        + f", and {len(toxic_comments)} of {len(comments)} sampled comments flagged toxic. "
        + f"Composite risk score is {risk:.3f}."
    )

    step2 = (
        f"The dominant signal driving this score is {top_signal} "
        f"({signals.get('device_reuse_signal', 'n/a')} device reuse, "
        f"{signals.get('account_age_signal', 'n/a')} account age). "
        + ("This matches a coordinated-campaign pattern rather than an isolated incident."
           if campaign else "No campaign clustering was found, suggesting an isolated account rather than coordinated abuse.")
    )

    step3 = f"Campaign context: {campaign_phrase}. " + (
        "High network density and velocity reinforce the risk score rather than contradicting it."
        if campaign and campaign.get("network_density", 0) > 0.5
        else "Campaign signal is weak or absent, so risk rests mainly on the account-level signals above."
    )

    if risk >= 0.55:
        verdict = "Suspend account and close the linked campaign cluster for review."
    elif risk >= 0.4:
        verdict = "Escalate to a senior analyst for manual review."
    elif total_reports == 0 and not campaign:
        verdict = "Close — insufficient evidence to act."
    else:
        verdict = "Monitor the account; re-evaluate if new reports arrive."

    return {
        "steps": [
            {"step": "Evidence Gathering", "content": step1},
            {"step": "Pattern Analysis", "content": step2},
            {"step": "Risk Correlation", "content": step3},
            {"step": "Verdict", "content": verdict},
        ],
        "mode": "fallback",
    }


class ReasoningEngine:

    def __init__(self, api_key: str | None = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model

    def reason(self, bundle: dict) -> dict:
        if self.api_key:
            try:
                return self._reason_via_groq(bundle)
            except Exception:
                return _rule_based_trace(bundle)
        return _rule_based_trace(bundle)

    def _reason_via_groq(self, bundle: dict) -> dict:
        from groq import Groq

        case = bundle["case"]
        account = bundle["account"]
        signals = bundle.get("signals") or {}
        campaign = bundle.get("campaign")
        reports = bundle.get("reports") or []
        comments = bundle.get("comments") or []

        toxic_comments = [c for c in comments if c.get("toxicity_label") not in (None, "clean")]
        campaign_phrase = (
            f"linked to campaign {campaign['campaign_id']} ({campaign['campaign_type']}), "
            f"network density {campaign['network_density']:.2f}"
            if campaign else "no known campaign link"
        )

        prompt = REASONING_PROMPT_TEMPLATE.format(
            case_id=case.get("case_id"), case_type=case.get("case_type"),
            priority=case.get("priority"), status=case.get("status"),
            account_id=account.get("account_id"),
            risk_score=account.get("risk_score"),
            account_age_signal=signals.get("account_age_signal", "n/a"),
            report_volume_signal=signals.get("report_volume_signal", "n/a"),
            device_reuse_signal=signals.get("device_reuse_signal", "n/a"),
            ip_region_signal=signals.get("ip_region_signal", "n/a"),
            toxicity_signal=signals.get("toxicity_signal", "n/a"),
            campaign_phrase=campaign_phrase,
            total_reports=sum(r["count"] for r in reports),
            top_reason=reports[0]["report_reason"] if reports else "n/a",
            toxic_comment_count=len(toxic_comments),
            total_comment_count=len(comments),
        )

        client = Groq(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        text = response.choices[0].message.content

        steps = []
        current_label, current_lines = None, []
        label_map = {
            "EVIDENCE GATHERING": "Evidence Gathering",
            "PATTERN ANALYSIS": "Pattern Analysis",
            "RISK CORRELATION": "Risk Correlation",
            "VERDICT": "Verdict",
        }
        for line in text.splitlines():
            stripped = line.strip().rstrip(":")
            if stripped.upper() in label_map:
                if current_label:
                    steps.append({"step": current_label, "content": " ".join(current_lines).strip()})
                current_label = label_map[stripped.upper()]
                current_lines = []
            elif current_label:
                current_lines.append(line.strip())
        if current_label:
            steps.append({"step": current_label, "content": " ".join(current_lines).strip()})

        if len(steps) != 4:
            return _rule_based_trace(bundle)

        return {"steps": steps, "mode": "llm"}


if __name__ == "__main__":
    from src.repositories.case_repository import CaseRepository

    bundle = CaseRepository().get_investigation_bundle("CASE-00082")
    engine = ReasoningEngine()
    result = engine.reason(bundle)

    print(f"Mode: {result['mode']}\n")
    for step in result["steps"]:
        print(f"-- {step['step']} --")
        print(step["content"])
        print()