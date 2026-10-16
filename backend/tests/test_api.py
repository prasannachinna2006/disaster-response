from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models import ReliefResource, RescueTeam
from app.main import create_app
from app.seed import seed_database


@pytest.fixture
def client(tmp_path: Path):
    database_path = tmp_path / "resqmesh-test.db"
    application = create_app(f"sqlite:///{database_path}")
    with TestClient(application) as test_client:
        with application.state.session_factory() as session:
            session.add(
                RescueTeam(
                    id="TEAM-01", name="Alpha Response", specialty="Urban search & rescue",
                    status="Available", member_count=8, location="North Sector",
                )
            )
            session.add_all(
                [
                    RescueTeam(
                        id="TEAM-02", name="Coastal Medical", specialty="Emergency medical",
                        status="Available", member_count=6, location="Harbor District",
                    ),
                    RescueTeam(
                        id="TEAM-04", name="Rapid Response 4", specialty="General response",
                        status="Available", member_count=5, location="East Sector",
                    ),
                ]
            )
            session.add(
                ReliefResource(
                    id="RES-WATER", name="Drinking water", quantity=184, unit="cases",
                    location="Central Market", status="Low stock",
                )
            )
            session.commit()
        yield test_client


def test_health_and_empty_incident_list(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/incidents").json() == []


def create_incident(client: TestClient, **overrides):
    payload = {
        "title": "Flooded community shelter",
        "description": "Water has entered the shelter.",
        "category": "Flooding",
        "priority": "P1",
        "status": "New",
        "location": "Harbor Shelter",
        "latitude": 19.07,
        "longitude": 72.86,
        "assistance": ["Medical team", "Water"],
    }
    payload.update(overrides)
    return client.post("/api/incidents", json=payload)


def test_incident_create_retrieve_filter_and_patch(client: TestClient):
    created = create_incident(client)
    assert created.status_code == 201
    incident = created.json()
    assert incident["id"].startswith("INC-")
    assert incident["assistance"] == ["Medical team", "Water"]
    assert client.get(f"/api/incidents/{incident['id']}").json()["title"] == "Flooded community shelter"

    filtered = client.get("/api/incidents", params={"priority": "P1", "status": "New"})
    assert len(filtered.json()) == 1
    updated = client.patch(
        f"/api/incidents/{incident['id']}",
        json={"status": "In progress", "priority": "P2"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "In progress"
    assert updated.json()["priority"] == "P2"
    assert client.get(f"/api/incidents/{incident['id']}").json()["priority"] == "P2"


def test_incident_delete_and_missing_records(client: TestClient):
    incident_id = create_incident(client).json()["id"]
    assert client.delete(f"/api/incidents/{incident_id}").status_code == 204
    assert client.get(f"/api/incidents/{incident_id}").status_code == 404
    assert client.patch("/api/incidents/missing", json={"status": "Resolved"}).status_code == 404
    assert client.delete("/api/incidents/missing").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "category": "Flood", "location": "Shelter"},
        {"title": "Bad priority", "category": "Flood", "location": "Shelter", "priority": "P0"},
        {"title": "Bad coordinates", "category": "Flood", "location": "Shelter", "latitude": 100, "longitude": 72},
        {"title": "Unpaired coordinates", "category": "Flood", "location": "Shelter", "latitude": 19},
    ],
)
def test_invalid_incident_payloads_are_rejected(client: TestClient, payload: dict):
    assert client.post("/api/incidents", json=payload).status_code == 422


def test_team_patch_and_manual_assignment(client: TestClient):
    team_response = client.post("/api/teams/TEAM-01/assignments", json={"incident_id": "missing"})
    assert team_response.status_code == 404
    assert client.get("/api/teams/absent").status_code == 404
    changed_team = client.patch("/api/teams/TEAM-01", json={"location": "Harbor District"})
    assert changed_team.status_code == 200
    assert changed_team.json()["location"] == "Harbor District"

    incident_id = create_incident(client).json()["id"]
    assert client.patch(
        "/api/teams/TEAM-01",
        json={"assigned_incident_id": "missing"},
    ).status_code == 404
    assigned = client.post("/api/teams/TEAM-01/assignments", json={"incident_id": incident_id})
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "Deployed"
    assert assigned.json()["assigned_incident_id"] == incident_id
    assert client.get(f"/api/incidents/{incident_id}").json()["status"] == "Assigned"
    assert client.post("/api/teams/TEAM-01/assignments", json={"incident_id": incident_id}).status_code == 409
    assert client.patch(
        "/api/teams/TEAM-04",
        json={"assigned_incident_id": incident_id},
    ).status_code == 409
    second_incident_id = create_incident(client, title="New assignment target").json()["id"]
    patched_team = client.patch(
        "/api/teams/TEAM-02",
        json={"assigned_incident_id": second_incident_id},
    )
    assert patched_team.status_code == 200
    assert patched_team.json()["status"] == "Deployed"
    assert client.get(f"/api/incidents/{second_incident_id}").json()["status"] == "Assigned"
    assert client.patch("/api/teams/absent", json={"status": "Available"}).status_code == 404
    assert client.patch("/api/teams/TEAM-01", json={"status": "Unknown"}).status_code == 422
    assert client.get("/api/teams/TEAM-01").json()["status"] == "Deployed"


def test_resource_endpoints_validate_and_persist(client: TestClient):
    resources = client.get("/api/resources").json()
    assert len(resources) == 1
    assert resources[0]["quantity"] == 184
    assert client.get("/api/resources/RES-WATER").json()["name"] == "Drinking water"
    assert client.get("/api/resources/missing").status_code == 404
    assert client.patch("/api/resources/missing", json={"quantity": 1}).status_code == 404
    updated = client.patch("/api/resources/RES-WATER", json={"quantity": 90, "status": "Monitor"})
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 90
    assert updated.json()["status"] == "Monitor"
    assert client.get("/api/resources/RES-WATER").json()["quantity"] == 90
    assert client.patch("/api/resources/RES-WATER", json={"quantity": -1}).status_code == 422
    assert client.get("/api/teams").json()[0]["id"] == "TEAM-01"


def test_data_survives_application_restart(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'persistent.db'}"
    first_app = create_app(database_url)
    with TestClient(first_app) as first_client:
        incident_id = create_incident(first_client).json()["id"]

    second_app = create_app(database_url)
    with TestClient(second_app) as second_client:
        assert second_client.get(f"/api/incidents/{incident_id}").status_code == 200
        assert second_client.get("/api/incidents").json()[0]["id"] == incident_id


def test_seed_is_idempotent(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'seeded.db'}"
    seed_database(database_url)
    seed_database(database_url)

    with TestClient(create_app(database_url)) as seeded_client:
        assert len(seeded_client.get("/api/incidents").json()) == 5
        assert len(seeded_client.get("/api/teams").json()) == 4
        assert len(seeded_client.get("/api/resources").json()) == 3
