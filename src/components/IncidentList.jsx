import { ArrowUpRight, Clock3, MapPin, Search, SlidersHorizontal } from 'lucide-react'
import StatusBadge from './StatusBadge'

export default function IncidentList({ incidents, priority, status, query, onPriority, onStatus, onQuery, onSelect, compact = false }) {
  return (
    <section className={`panel incident-panel ${compact ? 'incident-compact' : ''}`}>
      <div className="panel-heading"><div><h2>Recent incidents</h2><p>Persisted reports from the response area</p></div><span className="panel-count">{incidents.length} reports</span></div>
      <div className="incident-tools">
        <label className="search-box"><Search size={16} /><input aria-label="Search incidents by title or location" value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Search incidents or location…" /></label>
        <label className="filter-select"><SlidersHorizontal size={14} /><select aria-label="Filter by priority" value={priority} onChange={(event) => onPriority(event.target.value)}><option value="All">All priorities</option><option>P1</option><option>P2</option><option>P3</option></select></label>
        <label className="filter-select"><select aria-label="Filter by status" value={status} onChange={(event) => onStatus(event.target.value)}><option value="All">All statuses</option><option>New</option><option>Assigned</option><option>In progress</option><option>Resolved</option></select></label>
      </div>
      <div className="incident-list">
        {incidents.length ? incidents.map((incident) => (
          <article className="incident-row" key={incident.id}>
            <div className={`priority-rail rail-${incident.priority.toLowerCase()}`} />
            <div className="incident-main"><div className="incident-title-line"><span className={`priority-tag priority-${incident.priority.toLowerCase()}`}>{incident.priority}</span><h3>{incident.title}</h3></div><div className="incident-meta"><span><MapPin size={13} />{incident.location}</span><span><Clock3 size={13} />{incident.reported}</span><span className="incident-coordinates">{incident.coordinates}</span></div></div>
            <div className="incident-status"><StatusBadge>{incident.status}</StatusBadge><button type="button" className="text-button" onClick={() => onSelect(incident)}>View details <ArrowUpRight size={14} /></button></div>
          </article>
        )) : <div className="empty-state"><Search size={24} /><strong>No incidents match these filters</strong><span>Try a different priority, status, or search term.</span></div>}
      </div>
      {compact && <button className="view-all-button" type="button" onClick={() => onSelect(null)}>View all incidents <ArrowUpRight size={14} /></button>}
    </section>
  )
}
