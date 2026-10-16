from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("priority IN ('P1', 'P2', 'P3')", name="ck_incident_priority"),
        CheckConstraint(
            "status IN ('New', 'Assigned', 'In progress', 'Resolved')",
            name="ck_incident_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[str] = mapped_column(String(2), nullable=False, default="P3")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="New")
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    assistance: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class RescueTeam(Base):
    __tablename__ = "teams"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Available', 'Deployed', 'Unavailable')",
            name="ck_team_status",
        ),
        CheckConstraint("member_count >= 0", name="ck_team_member_count"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialty: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Available")
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_incident_id: Mapped[str | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )
    location: Mapped[str] = mapped_column(String(180), nullable=False, default="")


class ReliefResource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_resource_quantity"),
        CheckConstraint(
            "status IN ('Available', 'Low stock', 'Monitor', 'Unavailable')",
            name="ck_resource_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    location: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Available")


class SyncDevice(Base):
    __tablename__ = "sync_devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    peer_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    auth_token: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class SyncEvent(Base):
    __tablename__ = "sync_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_sync_event_id"),
        Index("ix_sync_events_status", "status"),
        Index("ix_sync_events_entity", "entity_type", "entity_id"),
        Index("ix_sync_events_source_device", "source_device_id", "status"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyncConflict(Base):
    __tablename__ = "sync_conflicts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    remote_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    local_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    remote_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SyncMetadata(Base):
    __tablename__ = "sync_metadata"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
