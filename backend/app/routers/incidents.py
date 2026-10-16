from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import IncidentCreate, IncidentPatch, IncidentRead, Priority, IncidentStatus
from ..services.incidents import create_incident, get_incident_or_404, list_incidents, to_incident_read, update_incident


router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRead])
def read_incidents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status_filter: IncidentStatus | None = Query(default=None, alias="status"),
    priority_filter: Priority | None = Query(default=None, alias="priority"),
    db: Session = Depends(get_db),
):
    return list_incidents(db, skip, limit, status_filter.value if status_filter else None, priority_filter.value if priority_filter else None)


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def add_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    return create_incident(db, payload)


@router.get("/{incident_id}", response_model=IncidentRead)
def read_incident(incident_id: str, db: Session = Depends(get_db)):
    return to_incident_read(get_incident_or_404(db, incident_id))


@router.patch("/{incident_id}", response_model=IncidentRead)
def patch_incident(incident_id: str, payload: IncidentPatch, db: Session = Depends(get_db)):
    return update_incident(db, incident_id, payload)


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = get_incident_or_404(db, incident_id)
    db.delete(incident)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
