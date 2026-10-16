import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, Droplets, Stethoscope, Users } from 'lucide-react'
import { api } from '../data/api'

const iconMap = { urgent: Stethoscope, info: Users, warning: Droplets }

function recommendationKind(agent = 'Incident Agent') {
  if (/Incident/i.test(agent)) return 'urgent'
  if (/Rescue/i.test(agent)) return 'info'
  return 'warning'
}

export default function RecommendedActions({ onReview }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const refresh = async () => {
      try {
        const payload = await api.loadAgentRecommendations()
        if (!active) return
        const recommendations = Array.isArray(payload?.recommendations) ? payload.recommendations : []
        setItems(recommendations.slice(0, 5))
        setError('')
      } catch (loadError) {
        if (active) setError(loadError.message)
      } finally {
        if (active) setLoading(false)
      }
    }

    refresh()
    return () => { active = false }
  }, [])

  const displayItems = items.filter((item) => item && (item.incident_id || item.resource_id || item.team_id || item.id))
  const note = loading ? 'Loading rule-based recommendations...' : error ? error : 'Rules are applied on demand from the live database.'

  return (
    <section className="panel recommendations-panel">
      <div className="panel-heading">
        <div>
          <h2>Recommended actions</h2>
          <p>Rule-based follow-ups from persisted records</p>
        </div>
        <span className="recommendation-count"><AlertTriangle size={13} /> {displayItems.length || 0} suggestions</span>
      </div>
      {error && <p className="muted">{error}</p>}
      {!error && (
        <div className="recommendation-list">
          {displayItems.length === 0 ? (
            <article className="recommendation-row recommendation-warning">
              <div className="recommendation-icon"><Droplets size={16} /></div>
              <div className="recommendation-copy">
                <strong>No active recommendations</strong>
                <span>{loading ? 'Checking current records...' : 'No unresolved incident data requires a rule-based action.'}</span>
              </div>
            </article>
          ) : (
            displayItems.map((item) => {
              const kind = recommendationKind(item.agent)
              const Icon = iconMap[kind]
              const title = item.agent === 'Rescue Agent' ? `${item.team_name ?? 'Team'} candidate` : item.incident_id ? `Incident ${item.incident_id}` : item.resource_name || item.team_name || item.agent
              const detail = item.explanation || item.suitability_explanation || item.resource_name || 'Rule-based recommendation pending human review.'
              const actionLabel = item.agent === 'Supply Agent' ? 'View supplies' : item.agent === 'Rescue Agent' ? 'Review assignment' : 'Review incident'

              return (
                <article className={`recommendation-row recommendation-${kind}`} key={item.id ?? `${item.agent}-${item.incident_id ?? 'general'}`}>
                  <div className="recommendation-icon"><Icon size={16} /></div>
                  <div className="recommendation-copy">
                    <strong>{title}</strong>
                    <span>{detail}</span>
                  </div>
                  <button type="button" className="recommendation-button" onClick={() => onReview?.({ ...item, action: actionLabel, incidentId: item.incident_id, target: item.resource_id ? 'supplies' : undefined })}>{actionLabel}<ArrowRight size={14} /></button>
                </article>
              )
            })
          )}
        </div>
      )}
      <p className="recommendation-note">{note}</p>
    </section>
  )
}
