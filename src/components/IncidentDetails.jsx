import { useEffect } from 'react'
import { ArrowUpRight, Check, Clock3, MapPin, ShieldAlert, Trash2, Users, X } from 'lucide-react'
import StatusBadge from './StatusBadge'

export default function IncidentDetails({ incident, onClose, onStatusChange, onResolve, onDelete, busy = false }) {
  useEffect(() => {
    const closeOnEscape = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  if (!incident) return null
  return (
    <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="incident-drawer" role="dialog" aria-modal="true" aria-labelledby="incident-title">
        <div className="drawer-top"><span className="eyebrow">{incident.id} <span className="eyebrow-dot">/</span> INCIDENT REPORT</span><button type="button" className="icon-button" aria-label="Close incident details" onClick={onClose}><X size={19} /></button></div>
        <div className="drawer-heading"><div className="incident-heading-icon"><ShieldAlert size={21} /></div><div><div className="detail-badges"><StatusBadge>{incident.priority}</StatusBadge><StatusBadge>{incident.status}</StatusBadge></div><h2 id="incident-title">{incident.title}</h2><span className="muted">{incident.category}</span></div></div>
        <p className="drawer-description">{incident.description}</p>
        <div className="detail-grid">
          <div><span><MapPin size={14} /> LOCATION</span><strong>{incident.location}</strong><small>{incident.coordinates}</small></div>
          <div><span><Clock3 size={14} /> CREATED</span><strong>{incident.reported}</strong><small>Stored report time</small></div>
        </div>
        <section className="drawer-section"><h3><Users size={15} /> Assistance needed</h3><div className="need-chips">{incident.assistance.map((need) => <span key={need}>{need}</span>)}</div></section>
        <section className="drawer-section"><h3><ArrowUpRight size={15} /> Suggested next steps</h3><ol className="next-steps"><li>Confirm incident details with the reporting contact.</li><li>Review the availability of nearby response teams.</li><li>Coordinate resources before dispatch.</li></ol></section>
        <div className="drawer-status"><label htmlFor="incident-status">Update incident status</label><select id="incident-status" value={incident.status} onChange={(event) => onStatusChange(incident.id, event.target.value)} disabled={busy || incident.status === 'Resolved'}><option>New</option><option>Assigned</option><option>In progress</option><option>Resolved</option></select></div>
        <div className="drawer-actions">
          <button className="button button-secondary" type="button" onClick={onClose}>Close details</button>
          <button className="button button-danger" type="button" onClick={() => onDelete(incident)} disabled={busy}><Trash2 size={14} /> Delete</button>
          {incident.status !== 'Resolved' && <button className="button button-success" type="button" onClick={() => onResolve(incident)} disabled={busy}><Check size={15} /> Mark resolved</button>}
        </div>
      </aside>
    </div>
  )
}
