from __future__ import annotations

import ipaddress
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Incident, SyncConflict, SyncDevice, SyncEvent, SyncMetadata
from ..schemas import SyncEventEnvelope

_LAN_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_device(db: Session, device_id: str | None = None) -> SyncDevice:
    if device_id is not None:
        device = db.get(SyncDevice, device_id)
        if device is not None:
            return device
        device = SyncDevice(device_id=device_id, peer_url="", auth_token="")
        db.add(device)
        db.flush()
        return device

    existing = db.scalar(select(SyncDevice).limit(1))
    if existing is not None:
        return existing

    device = SyncDevice(device_id=str(uuid.uuid4()), peer_url="", auth_token="")
    db.add(device)
    db.flush()
    return device


def get_or_create_device_id(db: Session) -> str:
    return ensure_device(db).device_id


def is_lan_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if address.is_multicast or address.is_reserved or address.is_unspecified:
        return False
    if address.is_loopback or address.is_link_local:
        return True
    return any(
        address.version == network.version and address in network
        for network in _LAN_NETWORKS
    )


def validate_peer_url(peer_url: str) -> str:
    try:
        parsed = urlsplit(peer_url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="peer_url must be a valid LAN HTTP URL") from exc
    if (
        parsed.scheme != "http"
        or host is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise HTTPException(status_code=422, detail="peer_url must be a LAN HTTP origin without credentials or path")
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="peer_url host must be a private or loopback IP address") from exc
    if not is_lan_address(address):
        raise HTTPException(status_code=422, detail="peer_url host must be a private or loopback IP address")
    return peer_url.rstrip("/")


def set_device_peer(db: Session, peer_url: str) -> SyncDevice:
    peer_url = validate_peer_url(peer_url)
    device = ensure_device(db)
    device.peer_url = peer_url
    device.auth_token = ""
    db.commit()
    db.refresh(device)
    return device


def get_sync_status(db: Session) -> dict[str, Any]:
    device = db.scalar(select(SyncDevice).limit(1))
    pending = db.scalar(select(func.count()).select_from(SyncEvent).where(SyncEvent.status == "pending")) or 0
    failed = db.scalar(select(func.count()).select_from(SyncEvent).where(SyncEvent.status == "failed")) or 0
    synced = db.scalar(select(func.count()).select_from(SyncEvent).where(SyncEvent.status == "synced")) or 0
    return {
        "status": "ok",
        "device_id": device.device_id if device else None,
        "peer_url": device.peer_url if device else "",
        "last_successful_sync_at": device.last_successful_sync_at.isoformat() if device and device.last_successful_sync_at else None,
        "pending_event_count": int(pending),
        "failed_event_count": int(failed),
        "synced_event_count": int(synced),
        "generated_at": utc_now().isoformat(),
        "rule_based": True,
        "authentication": "shared-secret-required",
    }


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except (TypeError, ValueError):
            return {}
        if isinstance(payload, dict):
            return payload
    elif isinstance(value, list):
        return {"items": value}
    return {}


def _incident_snapshot(incident: Incident) -> dict[str, Any]:
    assistance = []
    if incident.assistance:
        try:
            parsed = json.loads(incident.assistance)
        except (TypeError, ValueError):
            parsed = []
        if isinstance(parsed, list):
            assistance = parsed
    return {
        "title": incident.title,
        "description": incident.description,
        "category": incident.category,
        "priority": incident.priority,
        "status": incident.status,
        "location": incident.location,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "assistance": assistance,
    }


def _snapshot_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": payload["title"],
        "description": payload["description"],
        "category": payload["category"],
        "priority": payload["priority"],
        "status": payload["status"],
        "location": payload["location"],
        "latitude": payload["latitude"],
        "longitude": payload["longitude"],
        "assistance": payload["assistance"],
    }


def _latest_synced_snapshot(
    db: Session,
    incident_id: str,
    source_device_id: str,
) -> dict[str, Any] | None:
    event = db.scalar(
        select(SyncEvent)
        .where(
            SyncEvent.entity_id == incident_id,
            SyncEvent.source_device_id == source_device_id,
            SyncEvent.event_type == "incident.updated",
            SyncEvent.status == "synced",
        )
        .order_by(SyncEvent.created_at.desc())
        .limit(1)
    )
    if event is None:
        return None
    payload = _safe_dict(event.payload)
    if not all(key in payload for key in ("title", "description", "category", "priority", "status", "location", "latitude", "longitude", "assistance")):
        return None
    return _snapshot_from_payload(payload)


def list_pending_events(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(SyncEvent)
        .where(SyncEvent.status.in_(("pending", "failed")))
        .order_by(SyncEvent.created_at.asc())
    ).all()
    return [
        {
            "event_id": row.event_id,
            "event_type": row.event_type,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "source_device_id": row.source_device_id,
            "status": row.status,
            "retry_count": row.retry_count,
            "created_at": row.created_at.isoformat(),
            "payload": _safe_dict(row.payload),
        }
        for row in rows
    ]


def _set_sync_metadata(db: Session, key: str, value: str) -> None:
    record = db.get(SyncMetadata, key)
    if record is None:
        db.add(SyncMetadata(key=key, value=value))
    else:
        record.value = value


def _get_sync_metadata(db: Session, key: str) -> str | None:
    record = db.get(SyncMetadata, key)
    return record.value if record is not None else None


def _dashboard_snapshot(value: str) -> dict[str, Any]:
    try:
        snapshot = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Stored conflict snapshot is not valid JSON") from exc
    if not isinstance(snapshot, dict):
        raise ValueError("Stored conflict snapshot is not an object")
    return snapshot


def get_sync_dashboard(db: Session, skip: int = 0, limit: int = 50) -> dict[str, Any]:
    device = db.scalar(select(SyncDevice).limit(1))
    event_total = int(db.scalar(select(func.count()).select_from(SyncEvent)) or 0)
    conflict_total = int(db.scalar(select(func.count()).select_from(SyncConflict)) or 0)
    pending_count = int(
        db.scalar(
            select(func.count())
            .select_from(SyncEvent)
            .where(SyncEvent.status.in_(("pending", "failed")))
        )
        or 0
    )
    synced_count = int(
        db.scalar(
            select(func.count())
            .select_from(SyncEvent)
            .where(SyncEvent.status == "synced")
        )
        or 0
    )
    failed_count = int(
        db.scalar(
            select(func.count())
            .select_from(SyncEvent)
            .where(
                SyncEvent.status.in_(("pending", "failed")),
                SyncEvent.last_error.is_not(None),
            )
        )
        or 0
    )

    rows = db.scalars(
        select(SyncEvent)
        .order_by(SyncEvent.created_at.desc(), SyncEvent.event_id)
        .offset(skip)
        .limit(limit)
    ).all()
    events = [
        {
            "event_id": row.event_id,
            "incident_id": row.entity_id,
            "event_type": row.event_type,
            "created_at": row.created_at,
            "status": (
                "failed"
                if row.status in ("pending", "failed") and row.last_error
                else row.status
            ),
            "retry_count": row.retry_count,
            "last_error": (
                "Delivery failed; this event remains pending and can be retried."
                if row.status in ("pending", "failed") and row.last_error
                else None
            ),
        }
        for row in rows
    ]

    conflict_rows = db.scalars(
        select(SyncConflict)
        .order_by(SyncConflict.created_at.desc(), SyncConflict.id)
        .offset(skip)
        .limit(limit)
    ).all()
    conflicts = [
        {
            "incident_id": row.incident_id,
            "remote_event_id": row.remote_event_id,
            "local_event_id": row.local_event_id,
            "status": row.status,
            "created_at": row.created_at,
            "local_snapshot": _dashboard_snapshot(row.local_snapshot),
            "remote_snapshot": _dashboard_snapshot(row.remote_snapshot),
            "preserved_message": (
                "The receiving device preserved its local incident. "
                "Review both versions before taking any manual action."
            ),
        }
        for row in conflict_rows
    ]

    peer_url = device.peer_url if device and device.peer_url else None
    peer_reachable: bool | None = None
    if peer_url:
        try:
            peer_url = validate_peer_url(peer_url)
            response = httpx.get(
                f"{peer_url}/api/health",
                timeout=2.0,
                trust_env=False,
            )
            peer_reachable = (
                response.status_code == 200
                and response.json() == {"status": "ok"}
            )
        except (httpx.HTTPError, ValueError, TypeError):
            peer_reachable = False

    last_attempt_value = _get_sync_metadata(db, "last_sync_attempt_at")
    last_result_value = _get_sync_metadata(db, "last_sync_result")
    last_result = json.loads(last_result_value) if last_result_value else None

    return {
        "device_id": device.device_id if device else None,
        "peer_url": peer_url,
        "peer_configured": bool(peer_url),
        "peer_reachable": peer_reachable,
        "pending_event_count": pending_count,
        "synced_event_count": synced_count,
        "failed_delivery_count": failed_count,
        "conflict_count": conflict_total,
        "last_successful_sync_at": (
            device.last_successful_sync_at if device else None
        ),
        "last_sync_attempt_at": (
            datetime.fromisoformat(last_attempt_value)
            if last_attempt_value
            else None
        ),
        "last_sync_result": last_result,
        "generated_at": utc_now(),
        "events": events,
        "conflicts": conflicts,
        "event_total": event_total,
        "conflict_total": conflict_total,
        "skip": skip,
        "limit": limit,
    }


def _parse_assistance(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def create_incident_sync_event(db: Session, incident: Incident, source_device_id: str | None = None) -> SyncEvent:
    device_id = source_device_id or get_or_create_device_id(db)
    payload = {
        "incident_id": incident.id,
        "title": incident.title,
        "description": incident.description,
        "category": incident.category,
        "priority": incident.priority,
        "status": incident.status,
        "location": incident.location,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "assistance": _parse_assistance(incident.assistance),
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
    }
    event = SyncEvent(
        event_id=str(uuid.uuid4()),
        event_type="incident.updated",
        entity_type="incident",
        entity_id=incident.id,
        source_device_id=device_id,
        status="pending",
        retry_count=0,
        payload=json.dumps(payload, sort_keys=True),
    )
    db.add(event)
    db.flush()
    return event


def ack_event(db: Session, event_id: str, ack_device_id: str | None = None) -> SyncEvent:
    event = db.get(SyncEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' was not found")
    event.status = "synced"
    event.acked_at = utc_now()
    event.acknowledged_by = ack_device_id or event.source_device_id
    event.last_error = None
    device = db.get(SyncDevice, event.source_device_id)
    if device is not None:
        device.last_successful_sync_at = utc_now()
    db.commit()
    db.refresh(event)
    return event


def fail_event(db: Session, event_id: str, message: str) -> SyncEvent:
    event = db.get(SyncEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' was not found")
    event.status = "pending"
    event.last_error = message
    event.retry_count += 1
    db.commit()
    db.refresh(event)
    return event


def _duplicate_receive_result(
    existing: SyncEvent,
    incoming: SyncEventEnvelope,
    receiver_device_id: str,
) -> dict[str, Any]:
    same_event = (
        existing.status == "synced"
        and existing.event_type == incoming.event_type
        and existing.entity_type == incoming.entity_type
        and existing.entity_id == incoming.entity_id
        and existing.source_device_id == incoming.source_device_id
        and _safe_dict(existing.payload) == incoming.payload.model_dump(mode="json")
    )
    return {
        "status": "duplicate" if same_event else "conflict",
        "event_id": existing.event_id,
        "receiver_device_id": receiver_device_id,
    }


def receive_event(db: Session, event: SyncEventEnvelope) -> dict[str, Any]:
    existing_event = db.get(SyncEvent, event.event_id)
    if existing_event is not None:
        receiver_device_id = get_or_create_device_id(db)
        db.commit()
        return _duplicate_receive_result(
            existing_event,
            event,
            receiver_device_id,
        )

    entity_id = event.entity_id
    source_device_id = event.source_device_id
    incoming_payload = event.payload.model_dump(mode="json")
    incoming_snapshot = _snapshot_from_payload(incoming_payload)

    incident = db.get(Incident, entity_id)
    receiver_device_id = get_or_create_device_id(db)
    if incident is None:
        incident = Incident(
            id=entity_id,
            title=incoming_snapshot["title"],
            description=incoming_snapshot["description"],
            category=incoming_snapshot["category"],
            priority=incoming_snapshot["priority"],
            status=incoming_snapshot["status"],
            location=incoming_snapshot["location"],
            latitude=incoming_snapshot["latitude"],
            longitude=incoming_snapshot["longitude"],
            assistance=json.dumps(incoming_snapshot["assistance"]),
        )
        db.add(incident)
        db.flush()
    else:
        local_snapshot = _incident_snapshot(incident)
        if local_snapshot != incoming_snapshot:
            previous_snapshot = _latest_synced_snapshot(db, entity_id, source_device_id)
            if previous_snapshot == local_snapshot:
                for field, value in incoming_snapshot.items():
                    setattr(incident, field, json.dumps(value) if field == "assistance" else value)
                db.flush()
            else:
                conflict = SyncConflict(
                    id=str(uuid.uuid4()),
                    incident_id=incident.id,
                    remote_event_id=event.event_id,
                    local_snapshot=json.dumps(local_snapshot, sort_keys=True),
                    remote_snapshot=json.dumps(incoming_snapshot, sort_keys=True),
                    status="open",
                )
                db.add(conflict)
                db.add(
                    SyncEvent(
                        event_id=event.event_id,
                        event_type=event.event_type,
                        entity_type=event.entity_type,
                        entity_id=entity_id,
                        source_device_id=source_device_id,
                        status="conflict",
                        retry_count=0,
                        payload=json.dumps(incoming_payload, sort_keys=True),
                    )
                )
                db.commit()
                return {
                    "status": "conflict",
                    "event_id": event.event_id,
                    "incident_id": entity_id,
                    "receiver_device_id": receiver_device_id,
                }

    sync_event = SyncEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        entity_type=event.entity_type,
        entity_id=entity_id,
        source_device_id=source_device_id,
        status="synced",
        retry_count=0,
        payload=json.dumps(incoming_payload, sort_keys=True),
        acked_at=utc_now(),
        acknowledged_by="peer",
    )
    db.add(sync_event)
    db.commit()
    db.refresh(incident)
    return {
        "status": "accepted",
        "event_id": event.event_id,
        "incident_id": entity_id,
        "receiver_device_id": receiver_device_id,
    }


def deliver_pending_events(db: Session, shared_secret: str) -> dict[str, Any]:
    device = db.scalar(select(SyncDevice).limit(1))
    if device is None or not device.peer_url:
        raise HTTPException(status_code=409, detail="No LAN peer is configured")
    peer_url = validate_peer_url(device.peer_url)

    results: list[dict[str, str]] = []
    for outgoing in list_pending_events(db):
        event_id = outgoing["event_id"]
        try:
            response = httpx.post(
                f"{peer_url}/api/sync/receive",
                json=outgoing,
                headers={"X-Sync-Token": shared_secret},
                timeout=5.0,
            )
            response.raise_for_status()
            confirmation = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            fail_event(db, event_id, str(exc))
            results.append({"event_id": event_id, "status": "pending"})
            continue

        if (
            isinstance(confirmation, dict)
            and confirmation.get("event_id") == event_id
            and confirmation.get("status") in {"accepted", "duplicate"}
            and isinstance(confirmation.get("receiver_device_id"), str)
            and bool(confirmation["receiver_device_id"])
        ):
            ack_event(db, event_id, confirmation.get("receiver_device_id"))
            results.append({"event_id": event_id, "status": "synced"})
        else:
            fail_event(db, event_id, "Peer did not confirm acceptance or duplicate recognition")
            results.append({"event_id": event_id, "status": "pending"})

    result = {
        "peer_url": peer_url,
        "sent_count": sum(result["status"] == "synced" for result in results),
        "pending_count": sum(result["status"] == "pending" for result in results),
        "events": results,
    }
    _set_sync_metadata(db, "last_sync_attempt_at", utc_now().isoformat())
    _set_sync_metadata(db, "last_sync_result", json.dumps(result, sort_keys=True))
    db.commit()
    return result
