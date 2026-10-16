# Phase 4: Two-Instance Incident Sync Test Guide

This guide tests incident synchronization between two backend instances on the same Windows laptop. It uses separate temporary SQLite databases and does not use, reset, or delete the existing default database.

This verifies two local processes communicating over HTTP. It does **not** verify synchronization between two physical devices.

## Before you start

Open three PowerShell terminals. In the first two, one terminal will run each backend. Use the third terminal to configure peers, create an incident, and verify delivery.

Check whether ports 8000 and 8001 are already in use:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8001 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

If the existing backend is using port 8000, stop it with **Ctrl+C in the terminal where it was started** before starting Device A. Do not stop an unfamiliar process just to free the port.

Generate a random secret once:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep the generated value private. Enter the same value when prompted in all three terminals. Do not put the real secret in this report, a committed `.env` file, or logs.

## Start Device A on port 8000

In PowerShell terminal 1:

```powershell
Set-Location 'D:\disaster hackathon\backend'
.\.venv\Scripts\Activate.ps1

$env:RESQMESH_DATABASE_URL = 'sqlite:///D:\disaster hackathon\backend\data\phase4-device-a.db'
$secureSecret = Read-Host 'Enter the shared sync secret' -AsSecureString
$secretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureSecret)
try {
    $env:RESQMESH_SYNC_SHARED_SECRET = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPtr)
}

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave this terminal running. Do not run `python -m app.seed` for this test.

## Start Device B on port 8001

In PowerShell terminal 2:

```powershell
Set-Location 'D:\disaster hackathon\backend'
.\.venv\Scripts\Activate.ps1

$env:RESQMESH_DATABASE_URL = 'sqlite:///D:\disaster hackathon\backend\data\phase4-device-b.db'
$secureSecret = Read-Host 'Enter the same shared sync secret' -AsSecureString
$secretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureSecret)
try {
    $env:RESQMESH_SYNC_SHARED_SECRET = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPtr)
}

uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Leave this terminal running too.

The two processes use these separate SQLite files:

- `backend\data\phase4-device-a.db`
- `backend\data\phase4-device-b.db`

The existing default database, `backend\data\resqmesh.db`, is not selected by these commands.

## Configure the peer(s)

In PowerShell terminal 3, enter the same shared secret:

```powershell
$secureSecret = Read-Host 'Enter the same shared sync secret' -AsSecureString
$secretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureSecret)
try {
    $env:RESQMESH_SYNC_SHARED_SECRET = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPtr)
}
$syncHeaders = @{ 'X-Sync-Token' = $env:RESQMESH_SYNC_SHARED_SECRET }
```

Configure Device A to send to Device B:

```powershell
$peerBody = @{ peer_url = 'http://127.0.0.1:8001' } | ConvertTo-Json
Invoke-RestMethod -Method Post `
    -Uri 'http://127.0.0.1:8000/api/sync/device' `
    -Headers $syncHeaders `
    -ContentType 'application/json' `
    -Body $peerBody
```

To test the reverse direction later, configure Device B to send to Device A:

```powershell
$peerBody = @{ peer_url = 'http://127.0.0.1:8000' } | ConvertTo-Json
Invoke-RestMethod -Method Post `
    -Uri 'http://127.0.0.1:8001/api/sync/device' `
    -Headers $syncHeaders `
    -ContentType 'application/json' `
    -Body $peerBody
```

The inspected API uses `POST /api/sync/device` with the `peer_url` field. Hostnames are not accepted as peer addresses; use the loopback IP for this same-laptop test.

## Create an incident on A and send it to B

Create an incident using the existing incident API:

```powershell
$incidentBody = @{
    title = 'PHASE4-SYNC-TEST-A'
    description = 'Temporary local test incident for two-instance sync.'
    category = 'Infrastructure'
    priority = 'P2'
    status = 'New'
    location = 'Local test location'
    assistance = @()
} | ConvertTo-Json

$created = Invoke-RestMethod -Method Post `
    -Uri 'http://127.0.0.1:8000/api/incidents' `
    -ContentType 'application/json' `
    -Body $incidentBody

$created
$incidentId = $created.id
```

Send A's pending events to B:

```powershell
Invoke-RestMethod -Method Post `
    -Uri 'http://127.0.0.1:8000/api/sync/send' `
    -Headers $syncHeaders
```

The sender marks an event synced only after B returns a matching event ID with an `accepted` or `duplicate` confirmation. A conflict or failed request remains retryable.

## Verify the incident on B

Retrieve the incident from Device B using the ID returned by Device A:

```powershell
Invoke-RestMethod -Method Get `
    -Uri "http://127.0.0.1:8001/api/incidents/$incidentId"
```

Check Device A's authenticated sync status:

```powershell
Invoke-RestMethod -Method Get `
    -Uri 'http://127.0.0.1:8000/api/sync/status' `
    -Headers $syncHeaders
```

You can also list pending events on A:

```powershell
Invoke-RestMethod -Method Get `
    -Uri 'http://127.0.0.1:8000/api/sync/events' `
    -Headers $syncHeaders
```

After successful delivery, the event should no longer be pending.

## Safety and limitations

- Stop each backend with Ctrl+C when finished. The two test database files remain; they are separate from the default database.
- Do not run the test with your existing database URL. Do not run seed commands as part of this test.
- For real separate devices, the receiver must bind to its private LAN interface, and the sender must use the receiver's private IP. Restrict the Windows Defender Firewall inbound rule to the private network profile and intended peer. Do not port-forward or expose the service to the public internet.
- The sync API uses HTTP and does not encrypt traffic. Use only on a trusted isolated LAN or VPN.
- This guide describes the implementation and commands; no successful physical-device exchange has been verified.
- There is no automatic background retry, frontend sync status, or incident-deletion propagation.
