import { useEffect, useId, useRef, useState } from 'react'
import { Save, X } from 'lucide-react'

const emptyIncident = {
  title: '',
  description: '',
  category: '',
  priority: 'P3',
  status: 'New',
  location: '',
  latitude: '',
  longitude: '',
}

function initialValues(type, record) {
  if (type === 'incident') {
    return record
      ? {
          ...record,
          latitude: record.latitude ?? '',
          longitude: record.longitude ?? '',
        }
      : emptyIncident
  }
  if (type === 'team') {
    return {
      name: record.name,
      specialty: record.specialty,
      status: record.status,
      member_count: String(record.member_count),
      location: record.location,
      assigned_incident_id: record.assigned_incident_id ?? '',
    }
  }
  return {
    name: record.name,
    quantity: String(record.quantity),
    unit: record.unit,
    location: record.location,
    status: record.status,
  }
}

export default function RecordEditor({ type, record, incidents = [], busy = false, onClose, onSave }) {
  const titleId = useId()
  const firstInputRef = useRef(null)
  const [values, setValues] = useState(() => initialValues(type, record))
  const [error, setError] = useState('')
  const isCreate = type === 'incident' && !record
  const title = isCreate ? 'Create incident' : `Edit ${type === 'team' ? 'rescue team' : type}`

  useEffect(() => {
    firstInputRef.current?.focus()
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !busy) onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [busy, onClose])

  const change = (field) => (event) => {
    setValues((current) => ({ ...current, [field]: event.target.value }))
    setError('')
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (type === 'incident' && Boolean(values.latitude) !== Boolean(values.longitude)) {
      setError('Enter both latitude and longitude, or leave both blank.')
      return
    }
    const payload = type === 'incident'
      ? {
          title: values.title.trim(),
          description: values.description.trim(),
          category: values.category.trim(),
          priority: values.priority,
          status: values.status,
          location: values.location.trim(),
          latitude: values.latitude === '' ? null : Number(values.latitude),
          longitude: values.longitude === '' ? null : Number(values.longitude),
          assistance: record?.assistance || [],
        }
      : type === 'team'
        ? {
            name: values.name.trim(),
            specialty: values.specialty.trim(),
            status: values.assigned_incident_id && values.status === 'Available' ? 'Deployed' : values.status,
            member_count: Number(values.member_count),
            location: values.location.trim(),
            assigned_incident_id: values.assigned_incident_id || null,
          }
        : {
            name: values.name.trim(),
            quantity: Number(values.quantity),
            unit: values.unit.trim(),
            location: values.location.trim(),
            status: values.status,
          }
    try {
      await onSave(payload)
    } catch (saveError) {
      setError(saveError.message)
    }
  }

  return (
    <div className="modal-backdrop form-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <section className="confirm-modal record-editor" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <button className="icon-button modal-close" type="button" aria-label="Close form" onClick={onClose} disabled={busy}><X size={18} /></button>
        <span className="eyebrow">{isCreate ? 'NEW FIELD REPORT' : 'UPDATE LOCAL RECORD'}</span>
        <h2 id={titleId}>{title}</h2>
        <form onSubmit={submit}>
          {type === 'incident' && (
            <>
              <label className="form-field">Title<input ref={firstInputRef} value={values.title} onChange={change('title')} required maxLength={160} /></label>
              <label className="form-field">Category<input value={values.category} onChange={change('category')} required maxLength={80} /></label>
              <div className="form-grid">
                <label className="form-field">Priority<select value={values.priority} onChange={change('priority')}><option>P1</option><option>P2</option><option>P3</option></select></label>
                <label className="form-field">Status<select value={values.status} onChange={change('status')}><option>New</option><option>Assigned</option><option>In progress</option><option>Resolved</option></select></label>
              </div>
              <label className="form-field">Location<input value={values.location} onChange={change('location')} required maxLength={180} /></label>
              <label className="form-field">Description<textarea value={values.description} onChange={change('description')} rows="3" maxLength={10000} /></label>
              <div className="form-grid">
                <label className="form-field">Latitude (optional)<input type="number" step="any" min="-90" max="90" value={values.latitude} onChange={change('latitude')} /></label>
                <label className="form-field">Longitude (optional)<input type="number" step="any" min="-180" max="180" value={values.longitude} onChange={change('longitude')} /></label>
              </div>
              <p className="form-help">Coordinates are optional sample values, not live GPS. Enter both or leave both blank.</p>
            </>
          )}
          {type === 'team' && (
            <>
              <label className="form-field">Team name<input ref={firstInputRef} value={values.name} onChange={change('name')} required maxLength={120} /></label>
              <label className="form-field">Capability<input value={values.specialty} onChange={change('specialty')} required maxLength={120} /></label>
              <div className="form-grid">
                <label className="form-field">Availability<select value={values.status} onChange={change('status')}><option>Available</option><option>Deployed</option><option>Unavailable</option></select></label>
                <label className="form-field">Member count<input type="number" min="0" step="1" value={values.member_count} onChange={change('member_count')} required /></label>
              </div>
              <label className="form-field">Location description<input value={values.location} onChange={change('location')} maxLength={180} /></label>
              <label className="form-field">Assigned incident<select value={values.assigned_incident_id} onChange={change('assigned_incident_id')}><option value="">No assigned incident</option>{incidents.filter((incident) => (
                incident.id === record.assigned_incident_id
                || (record.status === 'Available' && incident.status !== 'Resolved' && !incident.assignedTeam)
              )).map((incident) => <option key={incident.id} value={incident.id}>{incident.id} · {incident.title}</option>)}</select></label>
              <p className="form-help">Only an available team can be linked to an unassigned active incident. This records coordination only and does not dispatch a team.</p>
            </>
          )}
          {type === 'resource' && (
            <>
              <label className="form-field">Resource name/type<input ref={firstInputRef} value={values.name} onChange={change('name')} required maxLength={120} /></label>
              <div className="form-grid">
                <label className="form-field">Quantity<input type="number" min="0" step="1" value={values.quantity} onChange={change('quantity')} required /></label>
                <label className="form-field">Unit<input value={values.unit} onChange={change('unit')} required maxLength={40} /></label>
              </div>
              <label className="form-field">Location description<input value={values.location} onChange={change('location')} maxLength={180} /></label>
              <label className="form-field">Availability<select value={values.status} onChange={change('status')}><option>Available</option><option>Low stock</option><option>Monitor</option><option>Unavailable</option></select></label>
            </>
          )}
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="modal-actions">
            <button className="button button-secondary" type="button" onClick={onClose} disabled={busy}>Cancel</button>
            <button className="button button-primary" type="submit" disabled={busy}><Save size={14} />{busy ? 'Saving…' : 'Save changes'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}
