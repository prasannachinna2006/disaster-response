import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronRight, CircleHelp, Clock3, Pencil, Plus, ShieldCheck, SlidersHorizontal, Users } from 'lucide-react'
import AgentsPanel from './components/AgentsPanel'
import IncidentDetails from './components/IncidentDetails'
import IncidentList from './components/IncidentList'
import MapPanel from './components/MapPanel'
import Modal from './components/Modal'
import NetworkNodes from './components/NetworkNodes'
import RecommendedActions from './components/RecommendedActions'
import ResourceStatus from './components/ResourceStatus'
import RecordEditor from './components/RecordEditor'
import Sidebar from './components/Sidebar'
import StatusBadge from './components/StatusBadge'
import SummaryCards from './components/SummaryCards'
import SyncDashboard from './components/SyncDashboard'
import Topbar from './components/Topbar'
import { api } from './data/api'
import { agents, nodes } from './data/mockData'
import './App.css'

const pageInfo = {
  dashboard: ['Operations overview', 'Situation overview'],
  incidents: ['Incident management', 'Incident register'],
  map: ['Operational picture', 'Disaster map'],
  teams: ['Response coordination', 'Rescue teams'],
  supplies: ['Resource coordination', 'Supplies & inventory'],
  agents: ['Decision support', 'AI agent center'],
  network: ['Connectivity overview', 'Network & nodes'],
  sync: ['Offline-first coordination', 'Sync status & conflicts'],
  settings: ['Workspace preferences', 'Settings'],
}

function PageHeading({ page, eyebrow }) {
  const [title, subtitle] = pageInfo[page]
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{subtitle} <span className="heading-dot" /> Phase 5 coordination database <span className="heading-dot" /> Local records</p>
      </div>
      <div className="heading-date"><Clock3 size={14} /> Response window <strong>Active</strong></div>
    </div>
  )
}

function DashboardPage({ incidents, visibleIncidents, teams, resources, onSelect, onReview, incidentProps }) {
  return (
    <>
      <PageHeading page="dashboard" eyebrow="RESPONSE OVERVIEW" />
      <SummaryCards incidents={incidents} teams={teams} resources={resources} />
      <div className="dashboard-columns">
        <div className="dashboard-main">
          <MapPanel />
          <IncidentList incidents={visibleIncidents} {...incidentProps} onSelect={onSelect} compact />
        </div>
        <div className="dashboard-side">
          <RecommendedActions onReview={onReview} />
          <ResourceStatus teams={teams} resources={resources} />
          <AgentsPanel />
        </div>
      </div>
    </>
  )
}

function IncidentsPage({ incidents, onSelect, incidentProps, onCreate }) {
  return (
    <>
      <PageHeading page="incidents" eyebrow="FIELD REPORTS" />
      <div className="page-intro">
        <div className="intro-icon"><ShieldCheck size={20} /></div>
        <div><strong>Incident register</strong><span>Review, search, filter, and update reports saved in the local database.</span></div>
        <span className="intro-count">{incidents.filter((incident) => incident.status !== 'Resolved').length} active</span>
        <button className="button button-primary intro-action" type="button" onClick={onCreate}><Plus size={15} /> Create Incident</button>
      </div>
      <IncidentList incidents={incidents} {...incidentProps} onSelect={onSelect} />
    </>
  )
}

function TeamsPage({ teams, incidents, onAssign, onEdit }) {
  const available = teams.filter((team) => team.status === 'Available')
  return (
    <>
      <PageHeading page="teams" eyebrow="RESPONSE COORDINATION" />
      <div className="page-intro">
        <div className="intro-icon"><Users size={20} /></div>
        <div><strong>{available.length} teams available</strong><span>Availability is stored; team locations are sample descriptions, not live tracking.</span></div>
        <span className="intro-count">{teams.length} total teams</span>
      </div>
      <section className="panel page-panel">
        <div className="panel-heading"><div><h2>Response teams</h2><p>Capabilities and assignments · local database</p></div><span className="demo-tag">LOCAL DATA</span></div>
        <div className="team-grid">
          {teams.map((team) => (
            <article className="team-card" key={team.id}>
              <div className="team-card-top"><div className="team-avatar"><Users size={18} /></div><StatusBadge>{team.status}</StatusBadge></div>
              <span className="eyebrow">{team.id}</span><h3>{team.name}</h3><p>{team.specialty}</p>
              <div className="team-location"><span>Last reported sector</span><strong>{team.location}</strong></div>
              <button className="button button-secondary team-edit" type="button" onClick={() => onEdit(team)}><Pencil size={13} /> Edit team</button>
              {team.status === 'Available' && <button className="button button-secondary team-assign" type="button" onClick={() => onAssign(team)}>Review assignment <ChevronRight size={14} /></button>}
            </article>
          ))}
        </div>
      </section>
      <div className="callout-info"><CircleHelp size={16} /><span>Confirmed assignments are stored locally. No rescue team is dispatched.</span></div>
      {incidents.length === 0 && <p className="muted">No incident reports are available.</p>}
    </>
  )
}

function SuppliesPage({ teams, resources, onEdit }) {
  const [category, setCategory] = useState('All resources')
  const availableTeams = teams.filter((team) => team.status === 'Available').length
  const inventoryRows = resources.map((item) => ({
    ...item,
    quantityLabel: `${item.quantity} ${item.unit}`,
    value: Math.min(100, item.quantity / (item.id === 'RES-FOOD' ? 1720 : item.id === 'RES-WATER' ? 650 : 190) * 100),
  }))
  inventoryRows.push({
    id: 'available-teams',
    name: 'Available teams',
    quantityLabel: `${availableTeams} of ${teams.length} teams`,
    value: teams.length ? availableTeams / teams.length * 100 : 0,
    status: teams.length && !availableTeams ? 'Unavailable' : 'Healthy',
  })
  const filtered = category === 'All resources'
    ? inventoryRows
    : inventoryRows.filter((item) => `${item.name} ${item.id}`.toLowerCase().includes(category.toLowerCase()))
  return (
    <>
      <PageHeading page="supplies" eyebrow="RESOURCE COORDINATION" />
      <div className="page-intro">
        <div className="intro-icon"><SlidersHorizontal size={19} /></div>
        <div><strong>Relief inventory overview</strong><span>Quantities are saved in the database; values are not live warehouse telemetry.</span></div>
        <span className="intro-count">{filtered.length} resource groups</span>
      </div>
      <section className="panel page-panel">
        <div className="panel-heading">
          <div><h2>Available resources</h2><p>Persisted inventory quantities and availability</p></div>
          <label className="filter-select"><select aria-label="Filter resource category" value={category} onChange={(event) => setCategory(event.target.value)}><option>All resources</option><option>Food</option><option>water</option><option>Medical</option><option>Available</option></select></label>
        </div>
        <div className="supply-table">
          <div className="supply-table-head"><span>RESOURCE</span><span>QUANTITY</span><span>STOCK LEVEL</span><span>STATUS</span><span>ACTION</span></div>
          {filtered.map((item) => (
            <div className="supply-table-row" key={item.id}>
              <strong>{item.name}</strong><span>{item.quantityLabel}</span>
              <div className="resource-progress"><i className={item.status === 'Low stock' ? 'progress-low' : ''} style={{ width: `${item.value}%` }} /></div>
              <StatusBadge>{item.status}</StatusBadge>
              {item.id === 'available-teams'
                ? <span className="muted">Team status</span>
                : <button className="text-button" type="button" onClick={() => onEdit(item)}>Edit resource <Pencil size={13} /></button>}
            </div>
          ))}
          {filtered.length === 0 && <div className="empty-state">No resources match that category.</div>}
        </div>
      </section>
      <ResourceStatus teams={teams} resources={resources} />
    </>
  )
}

function AgentsPage() {
  return (
    <>
      <PageHeading page="agents" eyebrow="ASSISTIVE WORKFLOWS" />
      <div className="callout-info"><CircleHelp size={16} /><span>All agent activity shown here is simulated. This phase does not run AI models or make automated operational decisions.</span></div>
      <div className="agents-page-grid">
        {agents.map((agent, index) => (
          <article className="panel agent-detail-card" key={agent.name}>
            <div className="agent-detail-head"><div className="agent-icon">0{index + 1}</div><StatusBadge>Demo ready</StatusBadge></div>
            <span className="eyebrow">ASSISTIVE WORKFLOW</span><h2>{agent.name}</h2><p>{agent.purpose}</p>
            <div className="agent-capability"><span>Mode</span><strong>Simulated · no inference</strong></div>
            <div className="agent-capability"><span>Operator control</span><strong>Human review required</strong></div>
          </article>
        ))}
      </div>
      <AgentsPanel full />
    </>
  )
}

function NetworkPage() {
  return (
    <>
      <PageHeading page="network" eyebrow="SIMULATED CONNECTIVITY" />
      <NetworkNodes full />
      <div className="network-stat-grid">
        <article className="panel network-stat"><span className="eyebrow">DEMO NODES</span><strong>12</strong><span>Example connected-node count</span></article>
        <article className="panel network-stat"><span className="eyebrow">PENDING SYNC</span><strong>{nodes.reduce((sum, node) => sum + node.pending, 0)}</strong><span>Example queued updates</span></article>
        <article className="panel network-stat"><span className="eyebrow">NETWORK STATUS</span><strong className="network-stat-status">Preview</strong><span>No peer connections established</span></article>
      </div>
      <div className="callout-warning"><CircleHelp size={16} /><span>This network illustration is simulated. View Sync Status for real backend incident delivery, pending events, and conflict records. Browser-side offline storage is not enabled.</span></div>
    </>
  )
}

function SettingsPage({ compact, onCompactChange, feedbackEnabled, onFeedbackChange }) {
  return (
    <>
      <PageHeading page="settings" eyebrow="WORKSPACE" />
      <section className="panel settings-panel">
        <div className="panel-heading"><div><h2>Workspace preferences</h2><p>Local presentation options for this demo session</p></div></div>
        <div className="settings-row">
          <div><strong>Compact incident rows</strong><span>Reduce spacing in incident lists.</span></div>
          <button className={`toggle-switch ${compact ? 'toggle-on' : ''}`} role="switch" aria-checked={compact} aria-label="Compact incident rows" onClick={() => onCompactChange(!compact)} type="button"><i /></button>
        </div>
        <div className="settings-row">
          <div><strong>In-app action feedback</strong><span>Show a confirmation toast after actions.</span></div>
          <button className={`toggle-switch ${feedbackEnabled ? 'toggle-on' : ''}`} role="switch" aria-checked={feedbackEnabled} aria-label="In-app action feedback" onClick={() => onFeedbackChange(!feedbackEnabled)} type="button"><i /></button>
        </div>
        <div className="settings-row"><div><strong>Environment</strong><span>Local API and SQLite records; maps and network remain simulated.</span></div><StatusBadge>Phase 5</StatusBadge></div>
        <div className="settings-row"><div><strong>Responder role</strong><span>Current sample workspace access.</span></div><strong className="setting-value">Field Responder</strong></div>
      </section>
      <div className="callout-info"><CircleHelp size={16} /><span>Preferences apply to this browser session only. Incident, team, and inventory records are stored by the backend.</span></div>
    </>
  )
}

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [incidents, setIncidents] = useState([])
  const [teams, setTeams] = useState([])
  const [resources, setResources] = useState([])
  const [loading, setLoading] = useState(true)
  const [reloadIndex, setReloadIndex] = useState(0)
  const [apiError, setApiError] = useState('')
  const [busyIncidentId, setBusyIncidentId] = useState('')
  const [confirmationBusy, setConfirmationBusy] = useState(false)
  const [selectedIncident, setSelectedIncident] = useState(null)
  const [priority, setPriority] = useState('All')
  const [status, setStatus] = useState('All')
  const [query, setQuery] = useState('')
  const [confirmation, setConfirmation] = useState(null)
  const [editor, setEditor] = useState(null)
  const [toast, setToast] = useState('')
  const [toastEnabled, setToastEnabled] = useState(true)
  const [compactMode, setCompactMode] = useState(false)
  const [editorBusy, setEditorBusy] = useState(false)
  const toastTimer = useRef(null)

  const showToast = useCallback((message) => {
    if (!toastEnabled) return
    setToast(message)
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(''), 3200)
  }, [toastEnabled])

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const [incidentRecords, teamRecords, resourceRecords] = await api.loadDashboard()
        if (!active) return
        const loadedIncidents = incidentRecords.map((incident) => {
          const assignedTeam = teamRecords.find((team) => team.assigned_incident_id === incident.id)
          const latitude = incident.latitude
          const longitude = incident.longitude
          const coordinates = latitude == null || longitude == null
            ? 'Coordinates not provided · not live GPS'
            : `${Math.abs(latitude).toFixed(4)}° ${latitude < 0 ? 'S' : 'N'}, ${Math.abs(longitude).toFixed(4)}° ${longitude < 0 ? 'W' : 'E'} · sample`
          return {
            ...incident,
            coordinates,
            reported: new Date(incident.created_at).toLocaleString(),
            assignedTeam: assignedTeam?.name,
          }
        })
        setApiError('')
        setIncidents(loadedIncidents)
        setTeams(teamRecords)
        setResources(resourceRecords)
      } catch (error) {
        if (active) setApiError(error.message)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [reloadIndex])

  const retryDataLoad = () => {
    setLoading(true)
    setApiError('')
    setReloadIndex((current) => current + 1)
  }

  const reloadDashboardData = () => {
    setLoading(true)
    setApiError('')
    setReloadIndex((current) => current + 1)
  }

  const navigate = useCallback((target) => {
    setPage(target)
    setMobileNavOpen(false)
    setSelectedIncident(null)
  }, [])

  useEffect(() => {
    const handleNavigate = (event) => navigate(event.detail)
    window.addEventListener('resq-navigate', handleNavigate)
    return () => window.removeEventListener('resq-navigate', handleNavigate)
  }, [navigate])

  const visibleIncidents = useMemo(() => incidents.filter((incident) => {
    const matchesPriority = priority === 'All' || incident.priority === priority
    const matchesStatus = status === 'All' || incident.status === status
    const needle = query.trim().toLowerCase()
    const matchesQuery = !needle || `${incident.title} ${incident.location} ${incident.category} ${incident.id}`.toLowerCase().includes(needle)
    return matchesPriority && matchesStatus && matchesQuery
  }), [incidents, priority, status, query])

  const handleStatusChange = (incidentId, nextStatus) => {
    if (nextStatus === 'Resolved') {
      const incident = incidents.find((item) => item.id === incidentId)
      setConfirmation({ type: 'resolve', incident })
      return
    }
    setBusyIncidentId(incidentId)
    api.updateIncident(incidentId, { status: nextStatus })
      .then((updated) => {
        const assignedTeam = teams.find((team) => team.assigned_incident_id === updated.id)?.name
        const updatedIncident = {
          ...updated,
          coordinates: selectedIncident?.coordinates || 'Coordinates not provided · not live GPS',
          reported: new Date(updated.created_at).toLocaleString(),
          assignedTeam,
        }
        setIncidents((current) => current.map((item) => item.id === incidentId ? updatedIncident : item))
        setSelectedIncident((current) => current?.id === incidentId ? updatedIncident : current)
        setApiError('')
        showToast(`Incident status saved as ${nextStatus}.`)
      })
      .catch((error) => {
        setApiError(error.message)
        showToast(error.message)
      })
      .finally(() => setBusyIncidentId(''))
  }

  const requestResolve = (incident) => setConfirmation({ type: 'resolve', incident })
  const requestAssignment = (incident, team) => {
    if (!team || team.status !== 'Available') {
      showToast('No available teams to assign.')
      return
    }
    setConfirmation({ type: 'assign', incident, team })
  }

  const completeConfirmation = async () => {
    const action = confirmation
    if (!action) return
    setConfirmationBusy(true)
    try {
      if (action.type === 'resolve') {
        const updated = await api.updateIncident(action.incident.id, { status: 'Resolved' })
        const updatedIncident = {
          ...updated,
          coordinates: action.incident.coordinates,
          reported: new Date(updated.created_at).toLocaleString(),
          assignedTeam: action.incident.assignedTeam,
        }
        setIncidents((current) => current.map((item) => item.id === action.incident.id ? updatedIncident : item))
        setSelectedIncident(null)
        showToast(`${action.incident.id} marked resolved and saved.`)
      } else if (action.type === 'delete') {
        await api.deleteIncident(action.incident.id)
        setSelectedIncident(null)
        showToast(`${action.incident.id} deleted.`)
      } else if (action.type === 'assign') {
        const updatedTeam = await api.assignTeam(action.team.id, action.incident.id)
        setTeams((current) => current.map((team) => team.id === updatedTeam.id ? updatedTeam : team))
        setIncidents((current) => current.map((item) => item.id === action.incident.id
          ? { ...item, status: item.status === 'New' ? 'Assigned' : item.status, assignedTeam: action.team.name }
          : item))
        showToast(`${action.team.name} assignment saved. No dispatch was made.`)
      }
      setApiError('')
      setConfirmation(null)
      reloadDashboardData()
    } catch (error) {
      setApiError(error.message)
      showToast(error.message)
    } finally {
      setConfirmationBusy(false)
    }
  }

  const saveRecord = async (payload) => {
    if (!editor) return
    setEditorBusy(true)
    try {
      if (editor.type === 'incident') {
        if (editor.record) await api.updateIncident(editor.record.id, payload)
        else await api.createIncident(payload)
      } else if (editor.type === 'team') {
        await api.updateTeam(editor.record.id, payload)
      } else {
        await api.updateResource(editor.record.id, payload)
      }
      const label = editor.type === 'incident' ? 'Incident' : editor.type === 'team' ? 'Rescue team' : 'Resource'
      setEditor(null)
      showToast(`${label} saved successfully.`)
      reloadDashboardData()
    } catch (error) {
      setApiError(error.message)
      throw error
    } finally {
      setEditorBusy(false)
    }
  }

  const selectIncident = (incident) => {
    if (!incident) {
      navigate('incidents')
      return
    }
    setSelectedIncident(incidents.find((item) => item.id === incident.id) || incident)
  }

  const handleReview = (recommendation) => {
    if (recommendation.target) {
      navigate(recommendation.target)
      return
    }
    const incident = incidents.find((item) => item.id === recommendation.incidentId)
    if (!incident) {
      showToast('This recommendation is no longer available.')
      return
    }
    if (recommendation.id === 'team') {
      const availableTeam = teams.find((team) => team.status === 'Available')
      if (!availableTeam) {
        showToast('No available teams to assign.')
        return
      }
      requestAssignment(incident, availableTeam)
    } else selectIncident(incident)
  }

  const listProps = { priority, status, query, onPriority: setPriority, onStatus: setStatus, onQuery: setQuery }
  const updateFeedback = (enabled) => {
    setToastEnabled(enabled)
    if (enabled) {
      setToast('In-app action feedback enabled.')
      window.clearTimeout(toastTimer.current)
      toastTimer.current = window.setTimeout(() => setToast(''), 3200)
    } else {
      window.clearTimeout(toastTimer.current)
      setToast('')
    }
  }

  return (
    <div className={`app-shell ${compactMode ? 'compact-ui' : ''}`}>
      <Topbar onNotify={() => showToast('No new demo notifications.')} />
      <div className="app-body">
        <Sidebar activePage={page} onNavigate={navigate} open={mobileNavOpen} onClose={() => setMobileNavOpen((open) => !open)} activeIncidentCount={incidents.filter((incident) => incident.status !== 'Resolved').length} />
        <main className="main-content">
          {(loading || apiError) && <div className={`api-notice ${apiError ? 'api-notice-error' : ''}`} role={apiError ? 'alert' : 'status'}>
            <span>{apiError || 'Loading incidents, teams, and resources from the local database…'}</span>
            {apiError && <button type="button" className="button button-secondary" onClick={retryDataLoad} disabled={loading}>{loading ? 'Retrying…' : 'Retry connection'}</button>}
          </div>}
          {page === 'dashboard' && <DashboardPage incidents={incidents} visibleIncidents={visibleIncidents} teams={teams} resources={resources} onSelect={selectIncident} onReview={handleReview} incidentProps={listProps} />}
          {page === 'incidents' && <IncidentsPage incidents={visibleIncidents} onSelect={selectIncident} incidentProps={listProps} onCreate={() => setEditor({ type: 'incident', record: null })} />}
          {page === 'map' && (
            <>
              <PageHeading page="map" eyebrow="OPERATIONAL PICTURE" />
              <MapPanel full />
              <div className="map-page-note"><CircleHelp size={16} /><span>This illustrative schematic is not a navigational map. Locations are sample data and do not represent live GPS. Future public map tiles may require internet connectivity; offline tile caching is not included.</span></div>
            </>
          )}
          {page === 'teams' && (
            <TeamsPage teams={teams} incidents={incidents} onEdit={(team) => setEditor({ type: 'team', record: team })} onAssign={(team) => {
              const incident = incidents.find((item) => item.status === 'New' && !item.assignedTeam)
                || incidents.find((item) => item.status !== 'Resolved' && !item.assignedTeam)
              if (!incident) {
                showToast('No unassigned active incidents are available.')
                return
              }
              requestAssignment(incident, team)
            }} />
          )}
          {page === 'supplies' && <SuppliesPage teams={teams} resources={resources} onEdit={(resource) => setEditor({ type: 'resource', record: resource })} />}
          {page === 'agents' && <AgentsPage />}
          {page === 'network' && <NetworkPage />}
          {page === 'sync' && <SyncDashboard />}
          {page === 'settings' && <SettingsPage compact={compactMode} onCompactChange={setCompactMode} feedbackEnabled={toastEnabled} onFeedbackChange={updateFeedback} />}
          <footer className="app-footer">
            <span>ResQMesh AI <i /> Phase 5 · Local coordination</span>
            <span><span className="footer-green-dot" /> Persistent local records · no live telemetry</span>
          </footer>
        </main>
      </div>
      <IncidentDetails incident={selectedIncident} onClose={() => setSelectedIncident(null)} onStatusChange={handleStatusChange} onResolve={requestResolve} onDelete={(incident) => setConfirmation({ type: 'delete', incident })} busy={busyIncidentId === selectedIncident?.id} />
      {editor && <RecordEditor type={editor.type} record={editor.record} incidents={incidents} busy={editorBusy} onClose={() => !editorBusy && setEditor(null)} onSave={saveRecord} />}
      {confirmation && (
        <Modal
          title={confirmation.type === 'resolve' ? 'Resolve this incident?' : confirmation.type === 'delete' ? 'Delete this incident?' : 'Confirm team assignment'}
          description={confirmation.type === 'resolve'
            ? `Mark “${confirmation.incident.title}” as resolved? This change will be saved in the local database.`
            : confirmation.type === 'delete'
              ? `Permanently delete “${confirmation.incident.title}” (${confirmation.incident.id}) from the local database? This cannot be undone.`
              : `Save ${confirmation.team.name} as assigned to “${confirmation.incident.title}”? This records coordination only; no real dispatch or external notification will occur.`}
          confirmLabel={confirmationBusy ? 'Saving…' : confirmation.type === 'resolve' ? 'Mark resolved' : confirmation.type === 'delete' ? 'Delete incident' : 'Save assignment'}
          tone={confirmation.type === 'resolve' || confirmation.type === 'delete' ? 'danger' : 'default'}
          onClose={() => !confirmationBusy && setConfirmation(null)}
          onConfirm={completeConfirmation}
          busy={confirmationBusy}
        />
      )}
      {toast && <div className="toast" role="status"><Check size={16} />{toast}<button type="button" aria-label="Dismiss notification" onClick={() => setToast('')}>×</button></div>}
    </div>
  )
}
