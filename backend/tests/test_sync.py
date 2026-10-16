import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Incident, RescueTeam, SyncConflict, SyncEvent
from app.services import sync as sync_service

SYNC_SECRET = "test-shared-sync-secret-that-is-long-enough"
AUTH = {"X-Sync-Token": SYNC_SECRET}
LOCAL_DASHBOARD_ORIGIN = {"Origin": "http://localhost:5173"}


def _make_incident_payload(**overrides):
    payload = {
        "title": "Remote bridge outage",
        "description": "Bridge access is blocked after rainfall.",
        "category": "Infrastructure",
        "priority": "P2",
        "status": "New",
        "location": "North Ridge Bridge",
        "latitude": 12.34,
        "longitude": 56.78,
        "assistance": ["Medical team", "Generator"],
    }
    payload.update(overrides)
    return payload


def _new_app(tmp_path: Path, filename: str):
    return create_app(f"sqlite:///{tmp_path / filename}", sync_shared_secret=SYNC_SECRET)


def _test_client(app):
    return TestClient(app, client=("192.168.1.10", 54321))


def _dashboard_client(app):
    return TestClient(app, client=("127.0.0.1", 54321))


def _mock_receiver(monkeypatch, peer_client: TestClient, token: str = SYNC_SECRET):
    def post(url, *, json, headers, timeout):
        assert url == "http://192.168.1.22:8000/api/sync/receive"
        assert headers == {"X-Sync-Token": token}
        assert timeout == 5.0
        response = peer_client.post("/api/sync/receive", json=json, headers=headers)
        return httpx.Response(
            response.status_code,
            json=response.json(),
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(sync_service.httpx, "post", post)


def _configure_peer(client: TestClient):
    return client.post(
        "/api/sync/device",
        json={"peer_url": "http://192.168.1.22:8000"},
        headers=AUTH,
    )


def test_incident_create_and_update_emit_durable_events(tmp_path: Path):
    app = _new_app(tmp_path, "sync-queue.db")
    with _test_client(app) as client:
        created = client.post("/api/incidents", json=_make_incident_payload())
        assert created.status_code == 201
        incident_id = created.json()["id"]
        updated = client.patch(f"/api/incidents/{incident_id}", json={"status": "In progress"})
        assert updated.status_code == 200

        pending = client.get("/api/sync/events", headers=AUTH).json()
        assert len(pending) == 2
        assert all(event["entity_id"] == incident_id for event in pending)
        assert all(event["status"] == "pending" for event in pending)
        assert pending[0]["payload"]["assistance"] == ["Medical team", "Generator"]
        assert pending[1]["payload"]["status"] == "In progress"

        with app.state.session_factory() as session:
            events = session.query(SyncEvent).filter_by(entity_id=incident_id).all()
            assert len(events) == 2
            assert all(event.event_type == "incident.updated" for event in events)
            assert events[0].source_device_id == events[1].source_device_id
            assert json.loads(events[0].payload)["incident_id"] == incident_id


def test_team_assignment_status_changes_emit_incident_events(tmp_path: Path):
    app = _new_app(tmp_path, "sync-team-assignment.db")
    with _test_client(app) as client:
        with app.state.session_factory() as session:
            session.add_all(
                [
                    RescueTeam(
                        id="TEAM-A",
                        name="Alpha",
                        specialty="Medical",
                        status="Available",
                        member_count=4,
                        location="North",
                    ),
                    RescueTeam(
                        id="TEAM-B",
                        name="Bravo",
                        specialty="Rescue",
                        status="Available",
                        member_count=5,
                        location="South",
                    ),
                ]
            )
            session.commit()

        first_id = client.post("/api/incidents", json=_make_incident_payload()).json()["id"]
        second_id = client.post(
            "/api/incidents",
            json=_make_incident_payload(title="Second assignment incident"),
        ).json()["id"]
        assert client.post(
            "/api/teams/TEAM-A/assignments",
            json={"incident_id": first_id},
        ).status_code == 200
        assert client.patch(
            "/api/teams/TEAM-B",
            json={"assigned_incident_id": second_id},
        ).status_code == 200

        with app.state.session_factory() as session:
            first_events = session.query(SyncEvent).filter_by(entity_id=first_id).all()
            second_events = session.query(SyncEvent).filter_by(entity_id=second_id).all()
            assert len(first_events) == 2
            assert len(second_events) == 2
            assert json.loads(first_events[-1].payload)["status"] == "Assigned"
            assert json.loads(second_events[-1].payload)["status"] == "Assigned"


def test_sync_endpoints_require_authentication_and_never_return_secret(tmp_path: Path):
    app = _new_app(tmp_path, "sync-auth.db")
    payload = {
        "event_id": "evt-auth-check",
        "event_type": "incident.updated",
        "entity_type": "incident",
        "entity_id": "INC-AUTH-CHECK",
        "source_device_id": "device-alpha",
        "payload": _make_incident_payload(incident_id="INC-AUTH-CHECK"),
    }
    with _test_client(app) as client:
        assert client.get("/api/sync/status").status_code == 401
        assert client.get("/api/sync/events").status_code == 401
        assert client.post("/api/sync/receive", json=payload).status_code == 401
        assert client.get("/api/sync/status", headers={"X-Sync-Token": "incorrect-token"}).status_code == 401
        assert client.post("/api/sync/device", json={"peer_url": "http://192.168.1.22:8000"}).status_code == 401
        assert client.post("/api/sync/receive", json=payload, headers=AUTH).json()["status"] == "accepted"

        status = client.get("/api/sync/status", headers=AUTH).json()
        assert status["authentication"] == "shared-secret-required"
        configuration = client.post(
            "/api/sync/device",
            json={"peer_url": "http://192.168.1.22:8000"},
            headers=AUTH,
        )
        assert configuration.status_code == 200
        assert SYNC_SECRET not in json.dumps(status)
        assert SYNC_SECRET not in configuration.text
        with app.state.session_factory() as session:
            assert session.query(Incident).filter_by(id="INC-AUTH-CHECK").count() == 1


def test_sync_authentication_fails_closed_without_strong_secret(tmp_path: Path):
    app = create_app(f"sqlite:///{tmp_path / 'sync-unconfigured.db'}", sync_shared_secret="short")
    with _test_client(app) as client:
        response = client.get("/api/sync/status", headers={"X-Sync-Token": "short"})
        assert response.status_code == 503


def test_sync_authentication_rejects_non_lan_clients(tmp_path: Path):
    app = _new_app(tmp_path, "sync-public-client.db")
    with TestClient(app, client=("8.8.8.8", 54321)) as client:
        response = client.get("/api/sync/status", headers=AUTH)
        assert response.status_code == 403


def test_invalid_payload_is_rejected_before_database_changes(tmp_path: Path):
    app = _new_app(tmp_path, "sync-invalid.db")
    invalid_payload = {
        "event_id": "evt-invalid-payload",
        "event_type": "incident.updated",
        "entity_type": "incident",
        "entity_id": "INC-INVALID",
        "source_device_id": "device-alpha",
        "payload": _make_incident_payload(incident_id="INC-INVALID", priority="P0"),
    }
    with _test_client(app) as client:
        response = client.post("/api/sync/receive", json=invalid_payload, headers=AUTH)
        assert response.status_code == 422
        with app.state.session_factory() as session:
            assert session.query(Incident).count() == 0
            assert session.query(SyncEvent).count() == 0


def test_duplicate_delivery_is_idempotent(tmp_path: Path):
    app = _new_app(tmp_path, "sync-duplicate.db")
    payload = {
        "event_id": "evt-duplicate-001",
        "event_type": "incident.updated",
        "entity_type": "incident",
        "entity_id": "INC-DUP-LOAD",
        "source_device_id": "device-alpha",
        "payload": _make_incident_payload(incident_id="INC-DUP-LOAD", title="Duplicate import"),
    }
    with _test_client(app) as client:
        first = client.post("/api/sync/receive", json=payload, headers=AUTH)
        second = client.post("/api/sync/receive", json=payload, headers=AUTH)
        assert first.status_code == 200
        assert first.json()["status"] == "accepted"
        assert second.status_code == 200
        assert second.json()["status"] == "duplicate"
        assert first.json()["receiver_device_id"] == second.json()["receiver_device_id"]
        changed_duplicate = {
            **payload,
            "payload": _make_incident_payload(
                incident_id="INC-DUP-LOAD",
                title="Different content using the same event ID",
            ),
        }
        conflicting_replay = client.post("/api/sync/receive", json=changed_duplicate, headers=AUTH)
        assert conflicting_replay.json()["status"] == "conflict"
        with app.state.session_factory() as session:
            assert session.query(Incident).filter_by(id="INC-DUP-LOAD").count() == 1
            assert session.query(SyncEvent).filter_by(event_id="evt-duplicate-001").count() == 1
            assert session.get(Incident, "INC-DUP-LOAD").title == "Duplicate import"


def test_http_delivery_and_duplicate_confirmation_acknowledge_only_after_peer_reply(
    tmp_path: Path, monkeypatch
):
    source_app = _new_app(tmp_path, "source-delivery.db")
    receiver_app = _new_app(tmp_path, "receiver-delivery.db")
    with _test_client(source_app) as source, _test_client(receiver_app) as receiver:
        created = source.post("/api/incidents", json=_make_incident_payload())
        assert created.status_code == 201
        incident_id = created.json()["id"]
        assert _configure_peer(source).status_code == 200
        _mock_receiver(monkeypatch, receiver)

        delivery = source.post("/api/sync/send", headers=AUTH)
        assert delivery.status_code == 200
        assert delivery.json()["sent_count"] == 1
        assert receiver.get(f"/api/incidents/{incident_id}").status_code == 200

        with source_app.state.session_factory() as session:
            event = session.query(SyncEvent).filter_by(entity_id=incident_id).one()
            assert event.status == "synced"
            assert event.acked_at is not None
            event.status = "pending"
            event.acked_at = None
            event.acknowledged_by = None
            session.commit()

        duplicate_delivery = source.post("/api/sync/send", headers=AUTH)
        assert duplicate_delivery.status_code == 200
        assert duplicate_delivery.json()["sent_count"] == 1
        with receiver_app.state.session_factory() as session:
            assert session.query(Incident).filter_by(id=incident_id).count() == 1
            assert session.query(SyncEvent).filter_by(entity_id=incident_id).count() == 1


def test_failed_http_delivery_stays_pending_and_retries(tmp_path: Path, monkeypatch):
    source_app = _new_app(tmp_path, "source-retry.db")
    receiver_app = _new_app(tmp_path, "receiver-retry.db")
    with _test_client(source_app) as source, _test_client(receiver_app) as receiver:
        created = source.post("/api/incidents", json=_make_incident_payload(title="Retry case"))
        incident_id = created.json()["id"]
        assert _configure_peer(source).status_code == 200
        with source_app.state.session_factory() as session:
            event = session.query(SyncEvent).filter_by(entity_id=incident_id).one()
            event.status = "failed"
            event.retry_count = 1
            session.commit()
        assert source.get("/api/sync/events", headers=AUTH).json()[0]["status"] == "failed"

        def fail_request(*args, **kwargs):
            raise httpx.ConnectError("temporary network failure")

        monkeypatch.setattr(sync_service.httpx, "post", fail_request)
        failed = source.post("/api/sync/send", headers=AUTH)
        assert failed.status_code == 200
        assert failed.json()["pending_count"] == 1
        with source_app.state.session_factory() as session:
            event = session.query(SyncEvent).filter_by(entity_id=incident_id).one()
            assert event.status == "pending"
            assert event.retry_count == 2
            assert event.acked_at is None

        _mock_receiver(monkeypatch, receiver)
        retried = source.post("/api/sync/send", headers=AUTH)
        assert retried.json()["sent_count"] == 1
        with source_app.state.session_factory() as session:
            event = session.query(SyncEvent).filter_by(entity_id=incident_id).one()
            assert event.status == "synced"
            assert event.retry_count == 2
            assert event.acked_at is not None


def test_peer_applies_later_update_when_no_local_conflict_exists(tmp_path: Path, monkeypatch):
    source_app = _new_app(tmp_path, "source-update.db")
    receiver_app = _new_app(tmp_path, "receiver-update.db")
    with _test_client(source_app) as source, _test_client(receiver_app) as receiver:
        incident = source.post("/api/incidents", json=_make_incident_payload()).json()
        incident_id = incident["id"]
        assert _configure_peer(source).status_code == 200
        _mock_receiver(monkeypatch, receiver)
        assert source.post("/api/sync/send", headers=AUTH).json()["sent_count"] == 1

        changed = source.patch(
            f"/api/incidents/{incident_id}",
            json={"description": "The bridge approach is now under water.", "priority": "P1"},
        )
        assert changed.status_code == 200
        updated_delivery = source.post("/api/sync/send", headers=AUTH)
        assert updated_delivery.json()["sent_count"] == 1

        remote_incident = receiver.get(f"/api/incidents/{incident_id}").json()
        assert remote_incident["description"] == "The bridge approach is now under water."
        assert remote_incident["priority"] == "P1"
        with receiver_app.state.session_factory() as session:
            assert session.query(SyncConflict).filter_by(incident_id=incident_id).count() == 0


def test_peer_with_different_shared_secret_cannot_receive_event(tmp_path: Path, monkeypatch):
    source_app = _new_app(tmp_path, "source-auth-failure.db")
    receiver_app = create_app(
        f"sqlite:///{tmp_path / 'receiver-auth-failure.db'}",
        sync_shared_secret="another-shared-secret-that-is-also-long-enough",
    )
    with _test_client(source_app) as source, _test_client(receiver_app) as receiver:
        incident = source.post("/api/incidents", json=_make_incident_payload()).json()
        assert _configure_peer(source).status_code == 200
        _mock_receiver(monkeypatch, receiver)

        response = source.post("/api/sync/send", headers=AUTH)
        assert response.status_code == 200
        assert response.json()["pending_count"] == 1
        with source_app.state.session_factory() as session:
            event = session.query(SyncEvent).filter_by(entity_id=incident["id"]).one()
            assert event.status == "pending"
            assert event.retry_count == 1
            assert event.acked_at is None
        with receiver_app.state.session_factory() as session:
            assert session.query(Incident).count() == 0
            assert session.query(SyncEvent).count() == 0


def test_invalid_peer_confirmation_does_not_acknowledge_event(tmp_path: Path, monkeypatch):
    app = _new_app(tmp_path, "sync-invalid-confirmation.db")
    with _test_client(app) as client:
        incident = client.post("/api/incidents", json=_make_incident_payload()).json()
        assert _configure_peer(client).status_code == 200

        def invalid_confirmation(url, **kwargs):
            return httpx.Response(
                200,
                json={
                    "status": "accepted",
                    "event_id": "not-the-outgoing-event",
                    "receiver_device_id": "receiver-device",
                },
                request=httpx.Request("POST", url),
            )

        monkeypatch.setattr(sync_service.httpx, "post", invalid_confirmation)
        response = client.post("/api/sync/send", headers=AUTH)
        assert response.json()["pending_count"] == 1
        with app.state.session_factory() as session:
            event = session.query(SyncEvent).filter_by(entity_id=incident["id"]).one()
            assert event.status == "pending"
            assert event.acked_at is None
            assert event.retry_count == 1


def test_conflict_is_preserved_and_not_acknowledged(tmp_path: Path, monkeypatch):
    source_app = _new_app(tmp_path, "source-conflict.db")
    receiver_app = _new_app(tmp_path, "receiver-conflict.db")
    with _test_client(source_app) as source, _test_client(receiver_app) as receiver:
        created = source.post("/api/incidents", json=_make_incident_payload(title="Conflict target")).json()
        incident_id = created["id"]
        assert _configure_peer(source).status_code == 200
        _mock_receiver(monkeypatch, receiver)

        assert source.post("/api/sync/send", headers=AUTH).json()["sent_count"] == 1
        assert receiver.patch(
            f"/api/incidents/{incident_id}",
            json={"description": "Local information stays intact.", "priority": "P1", "status": "Assigned"},
        ).status_code == 200
        assert source.patch(
            f"/api/incidents/{incident_id}",
            json={"description": "Remote information changed.", "status": "In progress"},
        ).status_code == 200

        response = source.post("/api/sync/send", headers=AUTH)
        assert response.status_code == 200
        assert response.json()["pending_count"] == 1
        with source_app.state.session_factory() as session:
            outgoing = session.query(SyncEvent).filter_by(entity_id=incident_id, status="pending").one()
            assert outgoing.status == "pending"
            assert outgoing.acked_at is None
        with receiver_app.state.session_factory() as session:
            local = session.get(Incident, incident_id)
            assert local.description == "Local information stays intact."
            assert local.status == "Assigned"
            assert local.priority == "P1"
            conflicts = session.query(SyncConflict).filter_by(incident_id=incident_id).all()
            assert len(conflicts) == 1
            assert conflicts[0].remote_event_id == response.json()["events"][0]["event_id"]
            received_event = session.query(SyncEvent).filter_by(event_id=conflicts[0].remote_event_id).one()
            assert received_event.status == "conflict"
        repeated = source.post("/api/sync/send", headers=AUTH)
        assert repeated.json()["pending_count"] == 1
        with receiver_app.state.session_factory() as session:
            assert session.query(SyncConflict).filter_by(incident_id=incident_id).count() == 1


def test_peer_configuration_rejects_non_lan_destinations(tmp_path: Path):
    app = _new_app(tmp_path, "sync-peer-validation.db")
    with _test_client(app) as client:
        response = client.post(
            "/api/sync/device",
            json={"peer_url": "http://example.com:8000"},
            headers=AUTH,
        )
        assert response.status_code == 422
        assert client.post(
            "/api/sync/device",
            json={"peer_url": "http://192.168.1.22:8000"},
            headers=AUTH,
        ).status_code == 200


def test_sync_preserves_existing_database_records_on_restart(tmp_path: Path):
    database_path = tmp_path / "persistent-sync.db"
    first_app = create_app(f"sqlite:///{database_path}", sync_shared_secret=SYNC_SECRET)
    with _test_client(first_app) as first_client:
        first_incident = first_client.post(
            "/api/incidents",
            json=_make_incident_payload(title="Persisted incident"),
        ).json()
        assert first_incident["id"].startswith("INC-")
        with first_app.state.session_factory() as session:
            original_event = session.query(SyncEvent).one()
            event_id = original_event.event_id
            device_id = original_event.source_device_id

    second_app = create_app(f"sqlite:///{database_path}", sync_shared_secret=SYNC_SECRET)
    with _test_client(second_app) as second_client:
        records = second_client.get("/api/incidents").json()
        assert len(records) == 1
        assert records[0]["title"] == "Persisted incident"
        with second_app.state.session_factory() as session:
            assert session.query(SyncEvent).count() == 1
            persisted_event = session.get(SyncEvent, event_id)
            assert persisted_event is not None
            assert persisted_event.source_device_id == device_id


def test_dashboard_is_loopback_origin_gated_and_empty_state_hides_secret(tmp_path: Path):
    app = _new_app(tmp_path, "sync-dashboard-empty.db")
    with _dashboard_client(app) as client:
        assert client.get("/api/sync/dashboard").status_code == 403
        assert client.get(
            "/api/sync/dashboard",
            headers={"Origin": "https://untrusted.example"},
        ).status_code == 403

        dashboard = client.get(
            "/api/sync/dashboard",
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert dashboard.status_code == 200
        body = dashboard.json()
        assert body["peer_configured"] is False
        assert body["peer_reachable"] is None
        assert body["pending_event_count"] == 0
        assert body["synced_event_count"] == 0
        assert body["failed_delivery_count"] == 0
        assert body["conflict_count"] == 0
        assert body["events"] == []
        assert body["conflicts"] == []
        assert body["last_successful_sync_at"] is None
        assert body["last_sync_attempt_at"] is None
        assert SYNC_SECRET not in dashboard.text

    with TestClient(app, client=("192.168.1.10", 54321)) as remote_client:
        response = remote_client.get(
            "/api/sync/dashboard",
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert response.status_code == 403


def test_dashboard_reports_pending_failures_history_and_conflict_snapshots(tmp_path: Path):
    app = _new_app(tmp_path, "sync-dashboard-history.db")
    with _dashboard_client(app) as client:
        incident = client.post(
            "/api/incidents",
            json=_make_incident_payload(title="Locally preserved report"),
        ).json()
        with app.state.session_factory() as session:
            pending = session.query(SyncEvent).filter_by(entity_id=incident["id"]).one()
            pending.event_id = "evt-dashboard-failed"
            pending.retry_count = 2
            pending.last_error = "Private internal transport failure detail"
            pending.created_at = datetime.now(timezone.utc) - timedelta(days=1)
            session.add(
                SyncEvent(
                    event_id="evt-dashboard-synced",
                    event_type="incident.updated",
                    entity_type="incident",
                    entity_id=incident["id"],
                    source_device_id="device-alpha",
                    status="synced",
                    retry_count=0,
                    payload="{}",
                )
            )
            session.add(
                SyncConflict(
                    id="conflict-dashboard-1",
                    incident_id=incident["id"],
                    remote_event_id="evt-dashboard-remote",
                    local_event_id="evt-dashboard-local",
                    local_snapshot=json.dumps(
                        {
                            "title": "Locally preserved report",
                            "description": "Local description",
                            "category": "Infrastructure",
                            "priority": "P2",
                            "status": "New",
                            "location": "North Ridge Bridge",
                            "latitude": 12.34,
                            "longitude": 56.78,
                            "assistance": ["Medical team"],
                        }
                    ),
                    remote_snapshot=json.dumps(
                        {
                            "title": "Remote revision",
                            "description": "Updated from peer",
                            "category": "Infrastructure",
                            "priority": "P1",
                            "status": "In progress",
                            "location": "North Ridge Bridge",
                            "latitude": 12.34,
                            "longitude": 56.78,
                            "assistance": ["Medical team", "Generator"],
                        }
                    ),
                    status="open",
                )
            )
            session.commit()

        response = client.get(
            "/api/sync/dashboard",
            params={"skip": 0, "limit": 2},
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert response.status_code == 200
        page = response.json()
        assert page["event_total"] == 2
        assert page["conflict_total"] == 1
        assert page["pending_event_count"] == 1
        assert page["synced_event_count"] == 1
        assert page["failed_delivery_count"] == 1
        assert len(page["events"]) == 2
        failed_event = next(event for event in page["events"] if event["status"] == "failed")
        assert failed_event["retry_count"] == 2
        assert failed_event["last_error"] == (
            "Delivery failed; this event remains pending and can be retried."
        )
        assert "Private internal transport failure detail" not in response.text
        conflict = page["conflicts"][0]
        assert conflict["incident_id"] == incident["id"]
        assert conflict["status"] == "open"
        assert conflict["local_snapshot"]["title"] == "Locally preserved report"
        assert conflict["remote_snapshot"]["title"] == "Remote revision"
        assert "preserved its local incident" in conflict["preserved_message"]
        assert SYNC_SECRET not in response.text
        assert client.get(f"/api/incidents/{incident['id']}").json()["title"] == (
            "Locally preserved report"
        )

        next_page = client.get(
            "/api/sync/dashboard",
            params={"skip": 1, "limit": 1},
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert next_page.status_code == 200
        assert next_page.json()["events"][0]["event_id"] == "evt-dashboard-failed"


def test_dashboard_peer_reachability_is_probed_not_assumed(tmp_path: Path, monkeypatch):
    app = _new_app(tmp_path, "sync-dashboard-peer.db")
    with _dashboard_client(app) as client:
        configured = _configure_peer(client)
        assert configured.status_code == 200

        def healthy_peer(url, *, timeout, trust_env):
            assert url == "http://192.168.1.22:8000/api/health"
            assert timeout == 2.0
            assert trust_env is False
            return httpx.Response(
                200,
                json={"status": "ok"},
                request=httpx.Request("GET", url),
            )

        monkeypatch.setattr(sync_service.httpx, "get", healthy_peer)
        response = client.get(
            "/api/sync/dashboard",
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert response.status_code == 200
        assert response.json()["peer_configured"] is True
        assert response.json()["peer_reachable"] is True
        assert SYNC_SECRET not in response.text

        def unavailable_peer(*args, **kwargs):
            raise httpx.ConnectError("private transport detail")

        monkeypatch.setattr(sync_service.httpx, "get", unavailable_peer)
        response = client.get(
            "/api/sync/dashboard",
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert response.status_code == 200
        assert response.json()["peer_reachable"] is False
        assert "private transport detail" not in response.text


def test_dashboard_send_keeps_secret_server_side_and_records_actual_result(
    tmp_path: Path, monkeypatch
):
    source_app = _new_app(tmp_path, "sync-dashboard-source.db")
    receiver_app = _new_app(tmp_path, "sync-dashboard-receiver.db")
    with _dashboard_client(source_app) as source, _test_client(receiver_app) as receiver:
        incident = source.post(
            "/api/incidents",
            json=_make_incident_payload(title="Dashboard delivery"),
        ).json()
        assert _configure_peer(source).status_code == 200
        _mock_receiver(monkeypatch, receiver)

        def healthy_peer(url, *, timeout, trust_env):
            assert trust_env is False
            return httpx.Response(
                200,
                json={"status": "ok"},
                request=httpx.Request("GET", url),
            )

        monkeypatch.setattr(sync_service.httpx, "get", healthy_peer)
        sent = source.post(
            "/api/sync/dashboard/send",
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert sent.status_code == 200
        assert sent.json()["sent_count"] == 1
        assert sent.json()["pending_count"] == 0
        assert SYNC_SECRET not in sent.text
        assert receiver.get(
            f"/api/incidents/{incident['id']}"
        ).status_code == 200

        dashboard = source.get(
            "/api/sync/dashboard",
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert dashboard.status_code == 200
        body = dashboard.json()
        assert body["pending_event_count"] == 0
        assert body["synced_event_count"] == 1
        assert body["last_sync_attempt_at"] is not None
        assert body["last_successful_sync_at"] is not None
        assert body["last_sync_result"]["sent_count"] == 1
        assert body["last_sync_result"]["pending_count"] == 0
        assert SYNC_SECRET not in dashboard.text


def test_dashboard_requires_configured_secret_and_send_reports_missing_peer(
    tmp_path: Path,
):
    unconfigured_app = create_app(
        f"sqlite:///{tmp_path / 'sync-dashboard-no-secret.db'}",
        sync_shared_secret="short",
    )
    with _dashboard_client(unconfigured_app) as client:
        response = client.get(
            "/api/sync/dashboard",
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert response.status_code == 503
        assert SYNC_SECRET not in response.text

    app = _new_app(tmp_path, "sync-dashboard-no-peer.db")
    with _dashboard_client(app) as client:
        response = client.post(
            "/api/sync/dashboard/send",
            headers=LOCAL_DASHBOARD_ORIGIN,
        )
        assert response.status_code == 409
