import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  CloudOff,
  LoaderCircle,
  RefreshCw,
  Send,
  ShieldAlert,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { api } from '../data/api'

const PAGE_SIZE = 50

function formatDate(value) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Not recorded' : date.toLocaleString()
}

function StatusTile({ label, value, detail, tone = '' }) {
  return (
    <article className={`sync-status-tile ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </article>
  )
}

function Snapshot({ label, snapshot }) {
  return (
    <section className="sync-snapshot">
      <h4>{label}</h4>
      <dl>
        <div><dt>Title</dt><dd>{snapshot.title}</dd></div>
        <div><dt>Priority / status</dt><dd>{snapshot.priority} · {snapshot.status}</dd></div>
        <div><dt>Category</dt><dd>{snapshot.category}</dd></div>
        <div><dt>Location</dt><dd>{snapshot.location}</dd></div>
        <div><dt>Description</dt><dd>{snapshot.description || 'No description'}</dd></div>
        <div><dt>Assistance</dt><dd>{snapshot.assistance.length ? snapshot.assistance.join(', ') : 'None recorded'}</dd></div>
      </dl>
    </section>
  )
}

function statusLabel(status) {
  return status === 'synced'
    ? 'Synchronized'
    : status === 'failed'
      ? 'Delivery failed'
      : status === 'conflict'
        ? 'Conflict'
        : 'Pending delivery'
}

export default function SyncDashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [actionResult, setActionResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [skip, setSkip] = useState(0)
  const [reload, setReload] = useState(0)
  const [refreshedAt, setRefreshedAt] = useState(null)

  const refreshDashboard = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    setError(null)
    try {
      const result = await api.loadSyncDashboard(skip, PAGE_SIZE)
      setDashboard(result)
      setRefreshedAt(new Date())
      return true
    } catch (requestError) {
      setError(requestError)
      return false
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [skip])

  useEffect(() => {
    let active = true
    api.loadSyncDashboard(skip, PAGE_SIZE)
      .then((result) => {
        if (!active) return
        setDashboard(result)
        setRefreshedAt(new Date())
        setError(null)
      })
      .catch((requestError) => {
        if (active) setError(requestError)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [skip, reload])

  const requestRefresh = () => {
    setLoading(true)
    setReload((value) => value + 1)
  }

  const syncNow = async () => {
    if (sending || loading) return
    setSending(true)
    setActionError(null)
    setActionResult(null)
    try {
      const result = await api.sendSyncNow()
      setActionResult(result)
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      await refreshDashboard(false)
      setSending(false)
    }
  }

  const connected = error ? Boolean(error.status) : Boolean(dashboard)
  const connectionLabel = loading && !dashboard
    ? 'Checking backend…'
    : connected
      ? error ? 'Backend responded · request rejected' : 'Local backend reachable'
      : 'Backend unavailable'
  const peerConfigured = dashboard?.peer_configured
  const peerReachable = dashboard?.peer_reachable
  const hasMore = dashboard
    ? skip + PAGE_SIZE < Math.max(dashboard.event_total, dashboard.conflict_total)
    : false
  const hasPrevious = skip > 0
  const actionMessage = actionError
    ? actionError.status === 401 || actionError.status === 403
      ? `Sync control was rejected: ${actionError.message}`
      : actionError.status === 503
        ? `Sync is not configured securely on the backend: ${actionError.message}`
        : actionError.status === 409
          ? 'No peer is configured. Configure a trusted LAN peer through the authenticated backend API, then retry.'
          : `Sync request failed: ${actionError.message}`
    : ''

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">OFFLINE-FIRST COORDINATION</span>
          <h1>Incident synchronization</h1>
          <p>Backend delivery state and conflict review <span className="heading-dot" /> No browser-held sync credentials</p>
        </div>
        <div className={`sync-connection-pill ${connected ? 'sync-connection-ok' : 'sync-connection-error'}`} role="status">
          {connected ? <Wifi size={14} /> : <CloudOff size={14} />}
          {connectionLabel}
        </div>
      </div>

      {error && (
        <div className="sync-notice sync-notice-error" role="alert">
          <CloudOff size={17} />
          <div>
            <strong>{error.status ? 'Dashboard request was rejected' : 'Cannot reach the local backend'}</strong>
            <span>{error.message} {dashboard && 'Showing the last successfully retrieved snapshot; it may be stale.'}</span>
          </div>
          <button type="button" className="button button-secondary" onClick={requestRefresh} disabled={loading}>
            Retry
          </button>
        </div>
      )}

      {actionMessage && (
        <div className="sync-notice sync-notice-error" role="alert">
          <ShieldAlert size={17} /><div><strong>Sync did not complete</strong><span>{actionMessage}</span></div>
        </div>
      )}

      {actionResult && (
        <div className={`sync-notice ${actionResult.pending_count ? 'sync-notice-error' : 'sync-notice-success'}`} role="status" aria-live="polite">
          {actionResult.pending_count ? <AlertTriangle size={17} /> : <CheckCircle2 size={17} />}
          <div>
            <strong>{actionResult.pending_count ? 'Sync attempt completed with pending deliveries' : 'Sync attempt confirmed'}</strong>
            <span>{actionResult.sent_count} acknowledged · {actionResult.pending_count} still pending</span>
          </div>
        </div>
      )}

      {loading && !dashboard ? (
        <section className="panel sync-empty-state" role="status">
          <LoaderCircle className="sync-spinner" size={20} /> Loading sync state from the backend…
        </section>
      ) : dashboard ? (
        <>
          <section className="panel sync-overview-panel">
            <div className="sync-panel-heading">
              <div>
                <span className="eyebrow">DEVICE STATUS</span>
                <h2>Peer and delivery overview</h2>
                <p>Counts and timestamps are returned by the local backend.</p>
              </div>
              <div className="sync-actions">
                <button className="button button-secondary" type="button" onClick={requestRefresh} disabled={loading || sending}>
                  <RefreshCw size={15} /> {loading ? 'Refreshing…' : 'Refresh'}
                </button>
                <button className="button button-primary" type="button" onClick={syncNow} disabled={loading || sending} aria-busy={sending}>
                  {sending ? <LoaderCircle className="sync-spinner" size={15} /> : <Send size={15} />}
                  {sending ? 'Sync in progress…' : 'Sync Now'}
                </button>
              </div>
            </div>

            <div className="sync-status-grid">
              <StatusTile
                label="Configured peer"
                value={peerConfigured ? dashboard.peer_url : 'Not configured'}
                detail={peerConfigured ? 'URL configured; reachability checked separately' : 'Configure a trusted LAN peer on the backend'}
                tone={peerConfigured ? '' : 'sync-tone-muted'}
              />
              <StatusTile
                label="Peer reachability"
                value={peerReachable == null ? 'Not checked' : peerReachable ? 'Reachable' : 'Unreachable'}
                detail={peerReachable == null ? 'No peer is configured' : peerReachable ? 'Peer health endpoint responded' : 'Last health check did not confirm availability'}
                tone={peerReachable === true ? 'sync-tone-green' : peerReachable === false ? 'sync-tone-red' : 'sync-tone-muted'}
              />
              <StatusTile label="Pending delivery" value={dashboard.pending_event_count} detail="Durable events awaiting confirmation" tone={dashboard.pending_event_count ? 'sync-tone-amber' : ''} />
              <StatusTile label="Synchronized" value={dashboard.synced_event_count} detail="Events acknowledged by a peer" tone="sync-tone-green" />
              <StatusTile label="Failed delivery" value={dashboard.failed_delivery_count} detail="Pending events with a recorded failure" tone={dashboard.failed_delivery_count ? 'sync-tone-red' : ''} />
              <StatusTile label="Open conflicts" value={dashboard.conflict_count} detail="Local incident version remains preserved" tone={dashboard.conflict_count ? 'sync-tone-red' : ''} />
              <StatusTile label="Last successful sync" value={formatDate(dashboard.last_successful_sync_at)} detail="Only set after peer confirmation" />
              <StatusTile label="Latest send attempt" value={formatDate(dashboard.last_sync_attempt_at)} detail={dashboard.last_sync_result ? `${dashboard.last_sync_result.sent_count} acknowledged · ${dashboard.last_sync_result.pending_count} pending` : 'No completed send attempt recorded'} />
            </div>

            <div className="sync-refresh-meta">
              <span><Clock3 size={13} /> Dashboard response received: {formatDate(refreshedAt?.toISOString())}</span>
              <span>{sending ? <><LoaderCircle className="sync-spinner" size={13} /> Sync in progress</> : peerReachable === false ? <><WifiOff size={13} /> Peer unavailable; queued events are retained</> : peerReachable ? <><Wifi size={13} /> Peer health check confirmed</> : 'Peer status unavailable'}</span>
            </div>
          </section>

          <section className="panel sync-history-panel">
            <div className="sync-panel-heading">
              <div>
                <span className="eyebrow">DURABLE QUEUE</span>
                <h2>Incident event history</h2>
                <p>{dashboard.event_total} recorded events · newest first</p>
              </div>
            </div>
            {dashboard.events.length ? (
              <div className="sync-event-list">
                {dashboard.events.map((event) => (
                  <article className="sync-event-row" key={event.event_id}>
                    <div className={`sync-event-icon sync-event-${event.status}`}>
                      {event.status === 'synced' ? <CheckCircle2 size={16} /> : event.status === 'conflict' || event.status === 'failed' ? <AlertTriangle size={16} /> : <Clock3 size={16} />}
                    </div>
                    <div className="sync-event-main">
                      <div className="sync-event-title">
                        <strong>{event.event_type}</strong>
                        <span className={`sync-state-badge sync-state-${event.status}`}>{statusLabel(event.status)}</span>
                      </div>
                      <span>Incident {event.incident_id} · Event {event.event_id}</span>
                      {event.last_error && <small className="sync-event-error">{event.last_error}</small>}
                    </div>
                    <div className="sync-event-meta"><span>{formatDate(event.created_at)}</span><span>{event.retry_count} retries</span></div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="sync-empty-state"><CheckCircle2 size={18} /> No synchronization events are recorded.</div>
            )}
          </section>

          <section className="panel sync-history-panel">
            <div className="sync-panel-heading">
              <div>
                <span className="eyebrow">MANUAL REVIEW</span>
                <h2>Incident conflicts</h2>
                <p>Conflicts are never automatically resolved or overwritten.</p>
              </div>
            </div>
            {dashboard.conflicts.length ? (
              <div className="sync-conflict-list">
                {dashboard.conflicts.map((conflict) => (
                  <article className="sync-conflict-card" key={conflict.remote_event_id}>
                    <div className="sync-conflict-header">
                      <div><strong>Incident {conflict.incident_id}</strong><span>Detected {formatDate(conflict.created_at)} · {conflict.status}</span></div>
                      <span className="sync-state-badge sync-state-conflict">Conflict detected</span>
                    </div>
                    <p className="sync-preserved-message"><ShieldAlert size={15} />{conflict.preserved_message}</p>
                    <div className="sync-snapshot-grid">
                      <Snapshot label="Preserved local version" snapshot={conflict.local_snapshot} />
                      <Snapshot label="Incoming peer version" snapshot={conflict.remote_snapshot} />
                    </div>
                    <small className="sync-conflict-event">Remote event {conflict.remote_event_id}{conflict.local_event_id ? ` · Local event ${conflict.local_event_id}` : ''}</small>
                  </article>
                ))}
              </div>
            ) : (
              <div className="sync-empty-state"><CheckCircle2 size={18} /> No incident conflicts are recorded.</div>
            )}
          </section>

          {(hasPrevious || hasMore) && (
            <nav className="sync-pagination" aria-label="Sync history pages">
              <span>Showing {Math.min(skip + 1, Math.max(dashboard.event_total, dashboard.conflict_total))}–{Math.min(skip + PAGE_SIZE, Math.max(dashboard.event_total, dashboard.conflict_total))} of {Math.max(dashboard.event_total, dashboard.conflict_total)}</span>
              <div>
                <button className="button button-secondary" type="button" onClick={() => { setLoading(true); setSkip((current) => Math.max(0, current - PAGE_SIZE)) }} disabled={!hasPrevious || loading}>Newer</button>
                <button className="button button-secondary" type="button" onClick={() => { setLoading(true); setSkip((current) => current + PAGE_SIZE) }} disabled={!hasMore || loading}>Older</button>
              </div>
            </nav>
          )}
        </>
      ) : !error ? (
        <section className="panel sync-empty-state" role="status">
          <CloudOff size={20} /> Sync dashboard is not currently available.
        </section>
      ) : null}
    </>
  )
}
