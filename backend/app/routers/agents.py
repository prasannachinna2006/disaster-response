from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.agents import generate_agent_recommendations, generate_incident_recommendation, get_agent_status

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/status")
def read_agent_status():
    return get_agent_status()


@router.get("/recommendations")
def read_agent_recommendations(db: Session = Depends(get_db)):
    return generate_agent_recommendations(db)


@router.get("/incidents/{incident_id}")
def read_incident_recommendation(incident_id: str, db: Session = Depends(get_db)):
    try:
        return generate_incident_recommendation(db, incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
