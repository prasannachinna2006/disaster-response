from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Incident, RescueTeam
from ..schemas import AssignmentCreate, IncidentStatus, TeamPatch, TeamRead
from ..services.sync import create_incident_sync_event


router = APIRouter(prefix="/api/teams", tags=["teams"])


def get_team_or_404(db: Session, team_id: str) -> RescueTeam:
    team = db.get(RescueTeam, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' was not found")
    return team


@router.get("", response_model=list[TeamRead])
def read_teams(db: Session = Depends(get_db)):
    return list(db.scalars(select(RescueTeam).order_by(RescueTeam.id)))


@router.get("/{team_id}", response_model=TeamRead)
def read_team(team_id: str, db: Session = Depends(get_db)):
    return get_team_or_404(db, team_id)


@router.patch("/{team_id}", response_model=TeamRead)
def patch_team(team_id: str, payload: TeamPatch, db: Session = Depends(get_db)):
    team = get_team_or_404(db, team_id)
    updates = payload.model_dump(exclude_unset=True)
    if (
        "assigned_incident_id" in updates
        and updates["assigned_incident_id"] is not None
        and updates["assigned_incident_id"] != team.assigned_incident_id
    ):
        incident_id = updates["assigned_incident_id"]
        incident = db.get(Incident, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' was not found")
        if incident.status == "Resolved":
            raise HTTPException(status_code=409, detail="A resolved incident cannot be assigned")
        if team.status != "Available":
            raise HTTPException(status_code=409, detail="Only available teams can be assigned")
        other_team = db.scalar(
            select(RescueTeam).where(
                RescueTeam.assigned_incident_id == incident_id,
                RescueTeam.id != team_id,
            )
        )
        if other_team:
            raise HTTPException(status_code=409, detail="Incident already has an assigned team")
    assignment_changed = (
        "assigned_incident_id" in updates
        and updates["assigned_incident_id"] is not None
        and updates["assigned_incident_id"] != team.assigned_incident_id
    )
    for field, value in updates.items():
        setattr(team, field, value.value if hasattr(value, "value") else value)
    if assignment_changed:
        team.status = "Deployed"
        incident = db.get(Incident, updates["assigned_incident_id"])
        if incident.status == "New":
            incident.status = "Assigned"
            db.flush()
            create_incident_sync_event(db, incident)
    db.commit()
    db.refresh(team)
    return team


@router.post("/{team_id}/assignments", response_model=TeamRead)
def assign_team(team_id: str, payload: AssignmentCreate, db: Session = Depends(get_db)):
    team = get_team_or_404(db, team_id)
    incident = db.get(Incident, payload.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{payload.incident_id}' was not found")
    if incident.status == IncidentStatus.RESOLVED.value:
        raise HTTPException(status_code=409, detail="A resolved incident cannot be assigned")
    if team.status != "Available":
        raise HTTPException(status_code=409, detail="Only available teams can be assigned")
    if team.assigned_incident_id:
        raise HTTPException(status_code=409, detail="Team already has an assigned incident")
    existing_team = db.scalar(
        select(RescueTeam).where(RescueTeam.assigned_incident_id == incident.id)
    )
    if existing_team:
        raise HTTPException(status_code=409, detail="Incident already has an assigned team")
    team.status = "Deployed"
    team.assigned_incident_id = incident.id
    if incident.status == IncidentStatus.NEW.value:
        incident.status = IncidentStatus.ASSIGNED.value
        db.flush()
        create_incident_sync_event(db, incident)
    db.commit()
    db.refresh(team)
    return team
