from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReliefResource
from ..schemas import ResourcePatch, ResourceRead


router = APIRouter(prefix="/api/resources", tags=["resources"])


def get_resource_or_404(db: Session, resource_id: str) -> ReliefResource:
    resource = db.get(ReliefResource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' was not found")
    return resource


@router.get("", response_model=list[ResourceRead])
def read_resources(db: Session = Depends(get_db)):
    return list(db.scalars(select(ReliefResource).order_by(ReliefResource.id)))


@router.get("/{resource_id}", response_model=ResourceRead)
def read_resource(resource_id: str, db: Session = Depends(get_db)):
    return get_resource_or_404(db, resource_id)


@router.patch("/{resource_id}", response_model=ResourceRead)
def patch_resource(resource_id: str, payload: ResourcePatch, db: Session = Depends(get_db)):
    resource = get_resource_or_404(db, resource_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(resource, field, value.value if hasattr(value, "value") else value)
    db.commit()
    db.refresh(resource)
    return resource
