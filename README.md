# ResQMesh AI — Phase 5

ResQMesh AI is a React/Vite disaster-response coordination dashboard backed by a FastAPI service and SQLite database. The dashboard keeps its existing layout while incident, rescue-team, and relief-resource records are loaded from persistent storage, with an offline-first incident synchronization dashboard for the durable Phase 4 LAN sync queue.

## Architecture

- **Frontend:** React 19, Vite, existing responsive CSS, Lucide icons, and the native `fetch` API (`src/`).
- **Backend:** FastAPI REST endpoints, Pydantic request/response validation, SQLAlchemy 2, and SQLite (`backend/app/`).
- **Database:** Created automatically on API startup at `backend/data/resqmesh.db` by default. Tables are initialized with SQLAlchemy metadata; no migration framework is needed for this initial schema.
- **Development seed:** `python -m app.seed` adds the sample Phase 1 incidents, teams, and resource rows once per table. It does not overwrite or append duplicates to non-empty tables.

The application does not implement general user authentication or dispatch. The incident-only sync API has a separate shared-secret gate and LAN source/destination restrictions; it is not a general-purpose security boundary. Coordinates and location descriptions in the seed data are examples, not live GPS. AI cards, the schematic map, and network/node values remain simulations.

## Windows PowerShell setup

Use two PowerShell terminals. These commands match the current project layout.

### Backend

```powershell
Set-Location 'D:\disaster hackathon\backend'
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m app.seed
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API documentation is at `http://127.0.0.1:8000/docs`. The optional seed command can be skipped if an empty database is desired.

### Frontend

In a second PowerShell terminal:

```powershell
Set-Location 'D:\disaster hackathon'
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). If the frontend runs on another origin, add it to `RESQMESH_CORS_ORIGINS` in `backend/.env` as a comma-separated list. Set `VITE_API_BASE_URL` before starting Vite to override the default `http://127.0.0.1:8000/api`.

### Database and configuration

The default database file is `backend/data/resqmesh.db`; its parent directory is created automatically. Backend settings are read from `backend/.env` when present, otherwise from process environment variables:

```dotenv
RESQMESH_DATABASE_URL=sqlite:///./data/resqmesh.db
RESQMESH_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
RESQMESH_SYNC_SHARED_SECRET=<same-random-secret-on-each-trusted-device>
```

Relative SQLite URLs are resolved from the backend working directory. To use a different database file, set `RESQMESH_DATABASE_URL` accordingly before starting the backend.
For sync, configure the same randomly generated secret of at least 32 characters in each device's private `backend/.env`; do not commit or share that file. The secret is read from environment configuration, never returned by the API, and must not be sent in logs or screenshots.

### LAN incident synchronization prototype

The backend has durable outgoing incident events, idempotent event reception, explicit conflict records, and an authenticated HTTP sender. Configure the receiving backend's LAN address on each node (substitute its reserved/private IPv4 address and port):

```powershell
$syncToken = '<same-random-secret-as-RESQMESH_SYNC_SHARED_SECRET>'
$headers = @{ 'X-Sync-Token' = $syncToken }
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/sync/device' -Headers $headers -ContentType 'application/json' -Body '{"peer_url":"http://192.168.1.22:8000"}'
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/sync/send' -Headers $headers
```

All `/api/sync/*` routes require `X-Sync-Token` and reject non-private/non-loopback/non-link-local client addresses. Peer URLs must be plain HTTP origins addressed by private, loopback, or link-local IP; hostnames and public addresses are intentionally rejected. On a second device, bind Uvicorn to that device's private LAN interface rather than `127.0.0.1` (for example, `uvicorn app.main:app --host 192.168.1.22 --port 8000`), then configure the other node with its address. Use a Windows Defender Firewall inbound rule restricted to the private network profile and intended peer's LAN address. Do not enable router port forwarding, public-profile inbound access, or expose this service to the public internet. HTTP does not encrypt traffic; use only on a trusted isolated LAN or VPN, and prefer a TLS-terminating private gateway if the network is not trusted.

`POST /api/sync/send` attempts outbound delivery of pending incident events. It marks an event synced only when the configured peer returns a matching event ID with `accepted` or `duplicate`; connection errors, invalid confirmations, and conflicts leave it pending for a later retry. A conflict is stored at the receiver without overwriting its local incident and is not acknowledged by the sender. Tests exercise two separately configured temporary SQLite databases through mocked HTTP calls; no successful exchange between two physical devices has been verified. This slice does not propagate incident deletions, and there is no frontend sync indicator or automatic background retry.

## API

All application endpoints are prefixed with `/api`. Validation errors return `422`, missing records return `404`, and requests that conflict with a current assignment return `409`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | API health check |
| `GET` | `/api/incidents` | List incidents; supports `skip`, `limit` (1–500), `status`, and `priority` query parameters |
| `POST` | `/api/incidents` | Create an incident (`201 Created`) |
| `GET` | `/api/incidents/{incident_id}` | Retrieve one incident |
| `PATCH` | `/api/incidents/{incident_id}` | Update provided incident fields |
| `DELETE` | `/api/incidents/{incident_id}` | Delete an incident (`204 No Content`) |
| `GET` | `/api/teams` | List rescue teams |
| `GET` | `/api/teams/{team_id}` | Retrieve one team |
| `PATCH` | `/api/teams/{team_id}` | Update team fields, status, or assignment reference |
| `POST` | `/api/teams/{team_id}/assignments` | Save an explicitly user-confirmed team-to-incident assignment; does not dispatch |
| `GET` | `/api/resources` | List relief resources |
| `GET` | `/api/resources/{resource_id}` | Retrieve one resource |
| `PATCH` | `/api/resources/{resource_id}` | Update quantity, availability, or other supported resource fields |

Sync routes for trusted peer operations require `X-Sync-Token` and a LAN client address: `GET /api/sync/status`, `GET /api/sync/events`, `POST /api/sync/device`, `POST /api/sync/receive`, and `POST /api/sync/send`. The local dashboard uses `GET /api/sync/dashboard?skip=0&limit=50` for status, paginated event history, and conflict snapshots, plus `POST /api/sync/dashboard/send` for the manual send action. These dashboard routes require a configured shared secret of at least 32 characters, a loopback client, and an `Origin` matching `RESQMESH_CORS_ORIGINS`; the browser never receives or sends the sync token. The dashboard send route invokes the same durable queue delivery service as the authenticated peer endpoint.

Incident priorities are `P1`, `P2`, or `P3`; incident statuses are `New`, `Assigned`, `In progress`, or `Resolved`; team statuses are `Available`, `Deployed`, or `Unavailable`. Resource quantities must be non-negative, and resource statuses are `Available`, `Low stock`, `Monitor`, or `Unavailable`. Latitude and longitude are optional and must be provided as a pair.

## Frontend integration

- The dashboard fetches incidents, teams, and resources from the API at startup and on browser refresh.
- Incident filters/search and the dashboard summary use fetched records. Incident status changes and resolving an incident persist through `PATCH`.
- The existing explicit assignment confirmation saves both the team assignment and associated incident status in a single backend transaction. It does not contact responders or perform dispatch.
- Incident creation is available on the incident register; incident deletion is available in the incident details drawer and requires confirmation.
- Rescue-team records can be edited from the teams page, including capability, availability, location, member count, and assignment. Resource name, quantity, unit, location, and availability can be edited from the supplies page. Negative quantities are rejected by both the form and API.
- Loading and API errors are shown in the dashboard with a retry action. Mutation failures are shown as an error notice and toast.
- The Sync Status page reads the backend's peer reachability probe, durable event history, delivery counts, last confirmed sync time, and conflict snapshots. Its Sync Now action calls the server-side delivery operation and refreshes the page after the attempt. It does not store browser-side incident data or the shared secret.
- The sync dashboard is intended for a browser running on the same machine as its backend: dashboard requests are restricted to loopback clients and configured frontend origins. If the backend or dashboard endpoint is unavailable, the sync page offers retry and labels a retained response as stale; the existing incident/team/resource screens continue to use the API as before.
- Agents, recommendation content, map illustration, and network/node values are still simulated. No AI inference, live map/GPS, automatic background retry, emergency messaging, or dispatch integration is included. Two backend instances on one laptop have exchanged an incident successfully; synchronization between physical devices has not been verified.

## Tests and production build

Run backend tests from the backend directory; they use a separate temporary SQLite database and do not access the development database:

```powershell
Set-Location 'D:\disaster hackathon\backend'
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

Validate the existing frontend:

```powershell
Set-Location 'D:\disaster hackathon'
npm run build
npm run lint
```

## Phase 5 sync dashboard and security notes

- The shared secret remains configured only on the backend as `RESQMESH_SYNC_SHARED_SECRET`; it must contain at least 32 characters. Do not place it in `VITE_*` settings, browser storage, or frontend code.
- Configure the actual Vite origin in `RESQMESH_CORS_ORIGINS` if it differs from the defaults (`http://localhost:5173,http://127.0.0.1:5173`). Restart the backend after changing environment configuration.
- The dashboard's local-origin/loopback gate is a browser integration restriction, not general user authentication. The application remains a local-development, single-user service without general API authorization.
- Peer reachability is checked through that peer's public `/api/health` response and is displayed separately from whether a peer URL is configured. A successful health check does not itself indicate that any event was delivered.
- Delivery uses HTTP and does not encrypt traffic. Use only on a trusted, restricted LAN or VPN. Do not expose sync endpoints to the public internet.
- Conflict details show both recorded snapshots and state that the receiving device's local incident was preserved. The dashboard does not resolve or overwrite conflicts.
- Dashboard history is returned in pages of up to 500 records; the frontend requests 50 at a time. Failed transport details are represented by a safe generic message rather than raw exception text.

## Known limitations

- This is a local-development, single-user application. It has no general user authentication, authorization, deployment hardening, or remote database. Sync's shared secret does not secure other API routes.
- Sample seed records and coordinates are illustrative only; resource levels and team locations are not live telemetry.
- Assignments persist as coordination data only. They do not dispatch people, send messages, or notify external services.
- AI agents, map, and network-node illustrations remain simulated. Browser-side offline persistence is not implemented; authoritative incident records remain in the backend database.
