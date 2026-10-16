from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Incident, ReliefResource, RescueTeam

AGENT_STATUS = [
    {
        "name": "Incident Agent",
        "status": "available",
        "description": "Prioritizes unresolved incidents using incident category, current priority, urgency and available evidence.",
        "rule_based": True,
    },
    {
        "name": "Rescue Agent",
        "status": "available",
        "description": "Ranks available teams against active incidents using specialty, assignment state and team availability.",
        "rule_based": True,
    },
    {
        "name": "Supply Agent",
        "status": "available",
        "description": "Summarizes stock levels and recommends allocation only when explicit demand data exists.",
        "rule_based": True,
    },
    {
        "name": "Coordination Engine",
        "status": "available",
        "description": "Aggregates incident, rescue and supply recommendations into a single rule-based decision view.",
        "rule_based": True,
    },
]

INCIDENT_RULES: list[dict[str, Any]] = [
    {
        "match": {"category": "Medical emergency", "priority": "P1"},
        "rule": "medical-urgency",
        "recommended_priority": "P1",
        "explanation": "Medical emergency cases with shelter, dehydration or urgent triage signals are treated as high-priority response needs.",
    },
    {
        "match": {"category": "Structural collapse", "priority": "P1"},
        "rule": "structural-collapse",
        "recommended_priority": "P1",
        "explanation": "Structural collapse scenarios require immediate coordination and rapid resource review.",
    },
    {
        "match": {"category": "Flooding", "priority": "P2"},
        "rule": "flooding-response",
        "recommended_priority": "P2",
        "explanation": "Flooding incidents that affect active shelter or access routes are elevated for rapid response planning.",
    },
    {
        "match": {"category": "Fire", "priority": "P2"},
        "rule": "fire-response",
        "recommended_priority": "P2",
        "explanation": "Active fire events receive elevated review when crews are working in constrained or hazardous conditions.",
    },
    {
        "match": {"category": "Blocked road", "priority": "P3"},
        "rule": "access-disruption",
        "recommended_priority": "P3",
        "explanation": "Access disruption is treated as a lower-priority incident unless it blocks urgent rescue routes.",
    },
]

TEAM_SKILL_RULES = {
    "Flooding": ["Flood & water rescue", "Emergency medical", "General response"],
    "Medical emergency": ["Emergency medical", "General response"],
    "Structural collapse": ["Urban search & rescue", "General response"],
    "Fire": ["General response", "Fire response"],
    "Blocked road": ["General response", "Road clearance crew", "Urban search & rescue"],
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_assistance(incident: Incident) -> list[str]:
    try:
        payload = json.loads(incident.assistance or "[]")
    except (TypeError, ValueError):
        return []
    return payload if isinstance(payload, list) else []


def _normalize_incident_text(incident: Incident) -> str:
    assistance = " ".join(_safe_assistance(incident))
    return " ".join(
        [
            incident.title or "",
            incident.description or "",
            incident.category or "",
            assistance,
        ]
    ).lower()


def _incident_recommendation_for(incident: Incident) -> dict[str, Any]:
    text = _normalize_incident_text(incident)
    if not text.strip():
        return {
            "id": f"incident-{incident.id}",
            "incident_id": incident.id,
            "agent": "Incident Agent",
            "current_priority": incident.priority,
            "recommended_priority": incident.priority,
            "explanation": "Incident data is incomplete; a manual review is required before assigning a new priority.",
            "rules": ["insufficient-information"],
            "confidence": "manual-review",
            "human_approval_required": True,
            "status": "insufficient-information",
        }

    category = incident.category or ""
    recommended_priority = incident.priority
    applied_rules: list[str] = []
    explanations: list[str] = []

    for rule in INCIDENT_RULES:
        if category == rule["match"]["category"]:
            recommended_priority = rule["recommended_priority"]
            applied_rules.append(rule["rule"])
            explanations.append(rule["explanation"])
            break

    if not applied_rules and "medical" in text:
        recommended_priority = "P1"
        applied_rules.append("medical-urgency")
        explanations.append("Medical keywords in the description are treated as an urgent high-priority indicator.")
    elif not applied_rules and ("collapse" in text or "structural" in text):
        recommended_priority = "P1"
        applied_rules.append("structural-collapse")
        explanations.append("Structural failure indicators trigger a P1 review when no higher-priority policy has already been assigned.")
    elif not applied_rules and ("flood" in text or "evacuation" in text):
        recommended_priority = "P2"
        applied_rules.append("flooding-response")
        explanations.append("Flooding and evacuation conditions trigger a multi-team response review.")
    elif not applied_rules and ("road" in text or "blocked" in text):
        recommended_priority = "P3"
        applied_rules.append("access-disruption")
        explanations.append("Access disruption is treated as a lower urgency risk unless it blocks rescue access.")

    if incident.status == "Resolved":
        return {
            "id": f"incident-{incident.id}",
            "incident_id": incident.id,
            "agent": "Incident Agent",
            "current_priority": incident.priority,
            "recommended_priority": incident.priority,
            "explanation": "Resolved incidents are excluded from active priority recommendations unless a manual review is explicitly requested.",
            "rules": ["resolved-incident-excluded"],
            "confidence": "strong",
            "human_approval_required": False,
            "status": "excluded",
        }

    if recommended_priority == incident.priority:
        explanation = (
            "Current priority is consistent with the active rule set. No change is recommended unless a human reviewer identifies new evidence."
        )
        confidence = "moderate" if applied_rules else "limited"
        human_approval_required = False
        status = "no-change"
    else:
        explanation = (
            f"Rule-based review suggests a change from {incident.priority} to {recommended_priority} because "
            + "; ".join(explanations)
        )
        confidence = "strong" if applied_rules else "limited"
        human_approval_required = True
        status = "change-recommended"

    return {
        "id": f"incident-{incident.id}",
        "incident_id": incident.id,
        "agent": "Incident Agent",
        "current_priority": incident.priority,
        "recommended_priority": recommended_priority,
        "explanation": explanation,
        "rules": applied_rules or ["default-priority-check"],
        "confidence": confidence,
        "human_approval_required": human_approval_required,
        "status": status,
    }


def _match_quality(team: RescueTeam, incident: Incident) -> tuple[int, str, list[str]]:
    text = _normalize_incident_text(incident)
    specialty = team.specialty.lower()
    score = 0
    reasons: list[str] = []
    if team.status == "Available":
        score += 2
        reasons.append("team is available")
    else:
        reasons.append(f"team status {team.status.lower()} is not actionable for an active assignment")
    if team.assigned_incident_id is None:
        score += 2
        reasons.append("team has no active assignment")
    else:
        reasons.append(f"team is already assigned to {team.assigned_incident_id}")
    if any(keyword.lower() in specialty for keyword in ("search", "rescue", "medical", "fire", "flood", "road", "general")):
        score += 1
        reasons.append("specialty is represented in the team profile")
    capability_match = "No clear capability match"
    for key, skills in TEAM_SKILL_RULES.items():
        if key.lower() in text and any(skill.lower() in specialty for skill in skills):
            capability_match = next(skill for skill in skills if skill.lower() in specialty)
            score += 3
            reasons.append(f"capability matches {key.lower()}")
            break
    return score, capability_match, reasons


def _rescue_recommendations_for(db: Session, incident: Incident) -> list[dict[str, Any]]:
    team_rows = db.scalars(select(RescueTeam).order_by(RescueTeam.member_count.desc(), RescueTeam.id)).all()
    candidate_rows = []
    for team in team_rows:
        if team.status != "Available":
            continue
        if team.assigned_incident_id is not None and team.assigned_incident_id != incident.id:
            continue
        score, capability_match, reasons = _match_quality(team, incident)
        if score == 0:
            continue
        candidate_rows.append(
            {
                "score": score,
                "team": team,
                "capability_match": capability_match,
                "reasons": reasons,
            }
        )

    candidate_rows.sort(key=lambda item: (-item["score"], item["team"].name.lower()))
    if not candidate_rows:
        return [
            {
                "id": f"rescue-{incident.id}-none",
                "incident_id": incident.id,
                "agent": "Rescue Agent",
                "team_id": None,
                "team_name": None,
                "suitability_explanation": "No available, unassigned team could be matched to this incident with sufficient rule-based evidence.",
                "capability_match": "No reliable match",
                "availability": "Unavailable or already committed",
                "assignment_status": "No recommendation",
                "missing_information": "The team roster, specialty, and active assignments available in the database do not support a safe recommendation.",
                "human_approval_required": True,
                "status": "insufficient-information",
            }
        ]

    results = []
    for candidate in candidate_rows[:3]:
        team = candidate["team"]
        results.append(
            {
                "id": f"rescue-{incident.id}-{team.id}",
                "incident_id": incident.id,
                "agent": "Rescue Agent",
                "team_id": team.id,
                "team_name": team.name,
                "suitability_explanation": (
                    f"{team.name} is available and its specialty profile is consistent with the incident requirements: "
                    + "; ".join(candidate["reasons"])
                ),
                "capability_match": candidate["capability_match"],
                "availability": team.status,
                "assignment_status": team.assigned_incident_id or "Unassigned",
                "missing_information": "Coordinate and travel distance checks are intentionally omitted unless a routing method and valid coordinates are supplied.",
                "human_approval_required": True,
                "status": "candidate",
            }
        )
    return results


def _supply_recommendations_for(db: Session, incident: Incident | None = None) -> list[dict[str, Any]]:
    resources = db.scalars(select(ReliefResource).order_by(ReliefResource.name)).all()
    recommendations: list[dict[str, Any]] = []
    for resource in resources:
        status = resource.status
        if status not in {"Low stock", "Monitor", "Unavailable"}:
            continue
        explanation_bits = [
            f"Current stock for {resource.name} is {resource.quantity} {resource.unit} and the status is {status}.",
        ]
        if incident is not None:
            incident_text = _normalize_incident_text(incident)
            if "medical" in incident_text and "medical" in resource.name.lower():
                explanation_bits.append("The incident requires medical response support and the resource is relevant to that need.")
            elif "flood" in incident_text and "water" in resource.name.lower():
                explanation_bits.append("The incident is flood-related and the resource is relevant to water support.")
            elif "shelter" in incident_text and "water" in resource.name.lower():
                explanation_bits.append("Shelter operations depend on water continuity and this stock is limited.")
            else:
                explanation_bits.append("The database does not contain a verified incident demand quantity for this resource, so allocation remains advisory.")
        else:
            explanation_bits.append("No specific incident demand is available in the database, so this is a stock availability summary rather than a demand-driven allocation.")

        recommendations.append(
            {
                "id": f"supply-{resource.id}",
                "incident_id": incident.id if incident else None,
                "agent": "Supply Agent",
                "resource_id": resource.id,
                "resource_name": resource.name,
                "available_quantity": resource.quantity,
                "unit": resource.unit,
                "status": resource.status,
                "suggested_allocation": None,
                "explanation": " ".join(explanation_bits),
                "constraints": [
                    "No allocation is made without explicit user approval.",
                    "No demand estimate is invented without stored demand data.",
                ],
                "human_approval_required": True,
                "status": "advisory",
            }
        )
    return recommendations


def _status_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "agents": AGENT_STATUS,
        "generated_at": _utc_now().isoformat(),
        "rule_based": True,
        "implementation_note": "All outputs are generated from persisted records using deterministic rules; they are not AI predictions.",
    }


def generate_agent_recommendations(db: Session) -> dict[str, Any]:
    incidents = db.scalars(
        select(Incident).where(Incident.status != "Resolved").order_by(Incident.priority.desc(), Incident.created_at.desc(), Incident.id)
    ).all()

    recommendations: list[dict[str, Any]] = []
    for incident in incidents:
        recommendations.append(_incident_recommendation_for(incident))
        recommendations.extend(_rescue_recommendations_for(db, incident))
        recommendations.extend(_supply_recommendations_for(db, incident))

    if not recommendations:
        recommendations = [
            {
                "id": "coordination-no-active-incidents",
                "agent": "Coordination Engine",
                "status": "no-active-incidents",
                "explanation": "No unresolved incidents are available for rule-based coordination review.",
                "human_approval_required": False,
            }
        ]

    payload = {
        "status": "ok",
        "generated_at": _utc_now().isoformat(),
        "rule_based": True,
        "agent_count": len(AGENT_STATUS),
        "recommendations": recommendations,
        "items": recommendations,
        "summary": {
            "incident_recommendations": sum(1 for item in recommendations if item.get("agent") == "Incident Agent"),
            "rescue_recommendations": sum(1 for item in recommendations if item.get("agent") == "Rescue Agent"),
            "supply_recommendations": sum(1 for item in recommendations if item.get("agent") == "Supply Agent"),
        },
    }
    return payload


def generate_incident_recommendation(db: Session, incident_id: str) -> dict[str, Any]:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise KeyError(f"Incident '{incident_id}' was not found")
    recommendation = _incident_recommendation_for(incident)
    return {
        "status": "ok",
        "incident_id": incident_id,
        "generated_at": _utc_now().isoformat(),
        "agent": "Incident Agent",
        "recommendations": [recommendation],
        "summary": recommendation,
    }


def get_agent_status() -> dict[str, Any]:
    return _status_payload()
