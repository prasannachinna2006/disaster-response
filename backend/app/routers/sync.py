import ipaddress
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    SyncDashboardRead,
    SyncEventEnvelope,
    SyncPeerConfig,
    SyncSendResult,
)
from ..services.sync import (
    deliver_pending_events,
    get_sync_dashboard,
    get_sync_status,
    is_lan_address,
    list_pending_events,
    receive_event,
    set_device_peer,
)

router = APIRouter(prefix="/api/sync", tags=["sync"])


def require_local_dashboard_access(request: Request) -> None:
    secret = request.app.state.sync_shared_secret
    if not isinstance(secret, str) or len(secret) < 32:
        raise HTTPException(status_code=503, detail="Sync authentication is not configured securely")
    try:
        remote_address = ipaddress.ip_address(request.client.host) if request.client else None
    except (TypeError, ValueError):
        remote_address = None
    if remote_address is None or not remote_address.is_loopback:
        raise HTTPException(status_code=403, detail="Sync dashboard controls are restricted to this device")
    origin = request.headers.get("origin")
    if not origin or origin not in request.app.state.sync_dashboard_origins:
        raise HTTPException(status_code=403, detail="Sync dashboard request origin is not allowed")


def require_sync_auth(
    request: Request,
    x_sync_token: Annotated[str | None, Header(alias="X-Sync-Token")] = None,
) -> str:
    secret = request.app.state.sync_shared_secret
    if not isinstance(secret, str) or len(secret) < 32:
        raise HTTPException(status_code=503, detail="Sync authentication is not configured securely")
    try:
        remote_address = ipaddress.ip_address(request.client.host) if request.client else None
    except (TypeError, ValueError):
        remote_address = None
    if remote_address is None or not is_lan_address(remote_address):
        raise HTTPException(status_code=403, detail="Sync is restricted to trusted LAN peers")
    if not x_sync_token or not hmac.compare_digest(
        x_sync_token.encode("utf-8"),
        secret.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid sync credentials")
    return secret


@router.get("/dashboard", response_model=SyncDashboardRead)
def read_sync_dashboard(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    _access: None = Depends(require_local_dashboard_access),
    db: Session = Depends(get_db),
):
    return get_sync_dashboard(db, skip=skip, limit=limit)


@router.post("/dashboard/send", response_model=SyncSendResult)
def send_dashboard_sync(
    request: Request,
    _access: None = Depends(require_local_dashboard_access),
    db: Session = Depends(get_db),
):
    return deliver_pending_events(db, request.app.state.sync_shared_secret)


@router.get("/status")
def read_sync_status(
    _auth: str = Depends(require_sync_auth),
    db: Session = Depends(get_db),
):
    return get_sync_status(db)


@router.get("/events")
def read_pending_events(
    _auth: str = Depends(require_sync_auth),
    db: Session = Depends(get_db),
):
    return list_pending_events(db)


@router.post("/receive")
def receive_sync_event(
    payload: SyncEventEnvelope,
    _auth: str = Depends(require_sync_auth),
    db: Session = Depends(get_db),
):
    return receive_event(db, payload)


@router.post("/send")
def send_pending_sync_events(
    auth: str = Depends(require_sync_auth),
    db: Session = Depends(get_db),
):
    return deliver_pending_events(db, auth)


@router.post("/device")
def configure_sync_device(
    payload: SyncPeerConfig,
    _auth: str = Depends(require_sync_auth),
    db: Session = Depends(get_db),
):
    device = set_device_peer(db, payload.peer_url)
    return {"device_id": device.device_id, "peer_url": device.peer_url}
