import { useEffect, useState } from 'react'
import { Bot, BrainCircuit, Map, Package, ScanSearch, Users } from 'lucide-react'
import { api } from '../data/api'

const iconMap = { 'Incident Agent': ScanSearch, 'Rescue Agent': Users, 'Supply Agent': Package, 'Coordination Engine': Map }

export default function AgentsPanel({ full = false }) {
  const [agents, setAgents] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const payload = await api.loadAgentStatus()
        if (!active) return
        setAgents(Array.isArray(payload?.agents) ? payload.agents : [])
        setError('')
      } catch (loadError) {
        if (active) setError(loadError.message)
      }
    }

    load()
    return () => { active = false }
  }, [])

  const displayAgents = agents.length ? agents : [
    { name: 'Incident Agent', status: 'available', description: 'Rule-based prioritization is not currently available.' },
  ]

  return (
    <section className={`panel agents-panel ${full ? 'agents-full' : ''}`}>
      <div className="panel-heading">
        <div>
          <h2>AI agents</h2>
          <p>Explainable coordination workflows</p>
        </div>
        <span className="demo-tag"><Bot size={13} /> RULE-BASED</span>
      </div>
      <div className="agents-list">
        {displayAgents.map((agent) => {
          const Icon = iconMap[agent.name] || ScanSearch
          return (
            <article className="agent-row" key={agent.name}>
              <div className="agent-icon"><Icon size={17} /></div>
              <div className="agent-copy">
                <strong>{agent.name}</strong>
                <span>{agent.description}</span>
              </div>
              <span className="agent-status"><i />{agent.status === 'available' ? 'Ready' : agent.status}</span>
            </article>
          )
        })}
      </div>
      {error ? <p className="muted">{error}</p> : null}
      <div className="agent-disclaimer"><BrainCircuit size={15} /><span>Rule-based coordination only. No external AI inference, no live dispatch.</span></div>
    </section>
  )
}
