from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IncidentStatus(str, Enum):
    NEW = "New"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In progress"
    RESOLVED = "Resolved"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TeamStatus(str, Enum):
    AVAILABLE = "Available"
    DEPLOYED = "Deployed"
    UNAVAILABLE = "Unavailable"


class ResourceStatus(str, Enum):
    AVAILABLE = "Available"
    LOW_STOCK = "Low stock"
    MONITOR = "Monitor"
    UNAVAILABLE = "Unavailable"


class IncidentFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=10000)
    category: str = Field(min_length=1, max_length=80)
    priority: Priority = Priority.P3
    status: IncidentStatus = IncidentStatus.NEW
    location: str = Field(min_length=1, max_length=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    assistance: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def require_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class IncidentCreate(IncidentFields):
    pass


class SyncIncidentPayload(IncidentFields):
    incident_id: str = Field(min_length=1, max_length=32)
    updated_at: datetime | None = None


class SyncEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(min_length=1, max_length=64)
    event_type: Literal["incident.updated"]
    entity_type: Literal["incident"]
    entity_id: str = Field(min_length=1, max_length=32)
    source_device_id: str = Field(min_length=1, max_length=64)
    status: Literal["pending", "failed"] | None = None
    retry_count: int | None = Field(default=None, ge=0)
    created_at: datetime | None = None
    payload: SyncIncidentPayload

    @model_validator(mode="after")
    def require_matching_incident_ids(self):
        if self.payload.incident_id != self.entity_id:
            raise ValueError("payload incident_id must match entity_id")
        return self


class SyncPeerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    peer_url: str = Field(min_length=1, max_length=255)


class SyncSendEventResult(BaseModel):
    event_id: str
    status: Literal["synced", "pending"]


class SyncSendResult(BaseModel):
    peer_url: str
    sent_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    events: list[SyncSendEventResult]


class SyncIncidentSnapshot(BaseModel):
    title: str
    description: str
    category: str
    priority: Priority
    status: IncidentStatus
    location: str
    latitude: float | None
    longitude: float | None
    assistance: list[str]


class SyncEventRead(BaseModel):
    event_id: str
    incident_id: str
    event_type: str
    created_at: datetime
    status: Literal["pending", "failed", "synced", "conflict"]
    retry_count: int = Field(ge=0)
    last_error: str | None


class SyncConflictRead(BaseModel):
    incident_id: str
    remote_event_id: str
    local_event_id: str | None
    status: str
    created_at: datetime
    local_snapshot: SyncIncidentSnapshot
    remote_snapshot: SyncIncidentSnapshot
    preserved_message: str


class SyncDashboardRead(BaseModel):
    device_id: str | None
    peer_url: str | None
    peer_configured: bool
    peer_reachable: bool | None
    pending_event_count: int = Field(ge=0)
    synced_event_count: int = Field(ge=0)
    failed_delivery_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    last_successful_sync_at: datetime | None
    last_sync_attempt_at: datetime | None
    last_sync_result: SyncSendResult | None
    generated_at: datetime
    events: list[SyncEventRead]
    conflicts: list[SyncConflictRead]
    event_total: int = Field(ge=0)
    conflict_total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)


class IncidentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=10000)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    priority: Priority | None = None
    status: IncidentStatus | None = None
    location: str | None = Field(default=None, min_length=1, max_length=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    assistance: list[str] | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def require_coordinate_pair(self):
        for field in self.model_fields_set - {"latitude", "longitude"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if "latitude" in self.model_fields_set and "longitude" not in self.model_fields_set:
            raise ValueError("latitude and longitude must be updated together")
        if "longitude" in self.model_fields_set and "latitude" not in self.model_fields_set:
            raise ValueError("latitude and longitude must be updated together")
        return self


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    category: str
    priority: Priority
    status: IncidentStatus
    location: str
    latitude: float | None
    longitude: float | None
    assistance: list[str]
    created_at: datetime
    updated_at: datetime


class TeamPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    specialty: str | None = Field(default=None, min_length=1, max_length=120)
    status: TeamStatus | None = None
    member_count: int | None = Field(default=None, ge=0)
    assigned_incident_id: str | None = None
    location: str | None = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in self.model_fields_set - {"assigned_incident_id"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    specialty: str
    status: TeamStatus
    member_count: int
    assigned_incident_id: str | None
    location: str


class ResourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    quantity: int | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    location: str | None = Field(default=None, max_length=180)
    status: ResourceStatus | None = None

    @model_validator(mode="after")
    def reject_null_fields(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    quantity: int
    unit: str
    location: str
    status: ResourceStatus


class AssignmentCreate(BaseModel):
    incident_id: str = Field(min_length=1, max_length=32)
