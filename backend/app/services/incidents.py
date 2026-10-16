import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Incident
from ..schemas import IncidentCreate, IncidentPatch
from ..services.sync import create_incident_sync_event


def to_incident_read(incident: Incident) -> dict:
    return {
        "id": incident.id,
        "title": incident.title,
        "description": incident.description,
        "category": incident.category,
        "priority": incident.priority,
        "status": incident.status,
        "location": incident.location,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "assistance": json.loads(incident.assistance),
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
    }


def list_incidents(
    db: Session, skip: int = 0, limit: int = 100, status: str | None = None, priority: str | None = None
) -> list[dict]:
    query = select(Incident).order_by(Incident.created_at.desc(), Incident.id)
    if status:
        query = query.where(Incident.status == status)
    if priority:
        query = query.where(Incident.priority == priority)
    return [to_incident_read(item) for item in db.scalars(query.offset(skip).limit(limit))]


def get_incident_or_404(db: Session, incident_id: str) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' was not found")
    return incident


def create_incident(db: Session, payload: IncidentCreate) -> dict:
    incident = Incident(
        id=f"INC-{uuid4().hex[:8].upper()}",
        **payload.model_dump(exclude={"assistance"}),
        assistance=json.dumps(payload.assistance),
    )
    db.add(incident)
    db.flush()
    create_incident_sync_event(db, incident)
    db.commit()
    db.refresh(incident)
    return to_incident_read(incident)


def update_incident(db: Session, incident_id: str, payload: IncidentPatch) -> dict:
    incident = get_incident_or_404(db, incident_id)
    updates = payload.model_dump(exclude_unset=True)
    if "assistance" in updates:
        updates["assistance"] = json.dumps(updates["assistance"])
    for field, value in updates.items():
        setattr(incident, field, value.value if hasattr(value, "value") else value)
    db.flush()
    create_incident_sync_event(db, incident)
    db.commit()
    db.refresh(incident)
    return to_incident_read(incident)
