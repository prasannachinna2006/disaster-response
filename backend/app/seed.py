import json
from pathlib import Path

from sqlalchemy import select

from .config import DATABASE_URL
from .database import Base, build_database
from .models import Incident, ReliefResource, RescueTeam


INCIDENTS = [
    ("INC-2048", "Residential building collapse", "Partial collapse reported in a four-storey residential block after prolonged heavy rainfall. Residents may be trapped on the upper floors.", "Structural collapse", "P1", "In progress", "North Riverside, Sector 4", 19.0768, 72.8782, ["Urban search & rescue", "Medical team", "Structural assessment"]),
    ("INC-2047", "Flooding near Central Market", "Rising water has reached the ground floors of nearby shops. Several residents are waiting on elevated walkways.", "Flooding", "P2", "Assigned", "Central Market, Ward 12", 19.0821, 72.8894, ["Water rescue", "Evacuation support", "Drinking water"]),
    ("INC-2046", "Medical emergency at shelter", "A shelter volunteer reports multiple people experiencing dehydration and one person requiring urgent medical assessment.", "Medical emergency", "P1", "New", "Harbor Community Shelter", 19.0698, 72.8655, ["Medical team", "Oral rehydration salts", "Drinking water"]),
    ("INC-2045", "Road blocked by fallen tree", "A large fallen tree is obstructing both lanes. The route is not currently passable for response vehicles.", "Blocked road", "P3", "New", "Old Port Road, Junction 3", 19.0614, 72.8917, ["Road clearance crew", "Route assessment"]),
    ("INC-2044", "Electrical fire in warehouse", "A small electrical fire was reported in a warehouse storage area. Crews extinguished the visible flames and checked for hotspots.", "Fire", "P2", "Resolved", "East Industrial Zone, Block C", 19.0913, 72.9041, ["Fire response", "Electrical safety inspection"]),
]
TEAMS = [
    ("TEAM-01", "Alpha Response", "Urban search & rescue", "Available", 8, "North Sector"),
    ("TEAM-02", "Coastal Medical", "Emergency medical", "Available", 6, "Harbor District"),
    ("TEAM-03", "Delta Water Rescue", "Flood & water rescue", "Deployed", 7, "Central Market"),
    ("TEAM-04", "Rapid Response 4", "General response", "Available", 5, "East Sector"),
]
RESOURCES = [
    ("RES-FOOD", "Food packs", 1240, "packs", "Central depot", "Available"),
    ("RES-WATER", "Drinking water", 184, "cases", "Central Market", "Low stock"),
    ("RES-MEDICAL", "Medical kits", 86, "kits", "Harbor Community Shelter", "Monitor"),
]


def seed_database(database_url: str = DATABASE_URL) -> None:
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        database_path = Path(database_url.removeprefix("sqlite:///"))
        database_path.parent.mkdir(parents=True, exist_ok=True)
    engine, session_factory = build_database(database_url)
    Base.metadata.create_all(bind=engine)
    with session_factory() as session:
        if not session.scalar(select(Incident.id).limit(1)):
            session.add_all(
                Incident(
                    id=item[0], title=item[1], description=item[2], category=item[3],
                    priority=item[4], status=item[5], location=item[6], latitude=item[7],
                    longitude=item[8], assistance=json.dumps(item[9]),
                )
                for item in INCIDENTS
            )
        if not session.scalar(select(RescueTeam.id).limit(1)):
            session.add_all(
                RescueTeam(id=item[0], name=item[1], specialty=item[2], status=item[3],
                           member_count=item[4], location=item[5])
                for item in TEAMS
            )
        if not session.scalar(select(ReliefResource.id).limit(1)):
            session.add_all(
                ReliefResource(id=item[0], name=item[1], quantity=item[2], unit=item[3],
                               location=item[4], status=item[5])
                for item in RESOURCES
            )
        session.commit()
    engine.dispose()


if __name__ == "__main__":
    seed_database()
    print(f"Sample records added to {DATABASE_URL}")
