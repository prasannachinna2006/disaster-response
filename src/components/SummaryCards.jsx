import { Activity, AlertOctagon, Package, Users } from 'lucide-react'

const iconMap = { incidents: AlertOctagon, teams: Users, supplies: Package, network: Activity }

export default function SummaryCards({ incidents, teams, resources }) {
  const active = incidents.filter((incident) => incident.status !== 'Resolved').length
  const p1 = incidents.filter((incident) => incident.priority === 'P1' && incident.status !== 'Resolved').length
  const availableTeams = teams.filter((team) => team.status === 'Available').length
  const inventoryQuantity = resources.reduce((total, resource) => total + resource.quantity, 0)
  const cards = [
    { title: 'Active incidents', value: String(active).padStart(2, '0'), detail: `${p1} require immediate attention`, icon: 'incidents', tone: 'red', foot: 'Response area' },
    { title: 'Available rescue teams', value: `${availableTeams}`, detail: `of ${teams.length} teams ready`, icon: 'teams', tone: 'blue', foot: 'Stored team availability' },
    { title: 'Supplies available', value: inventoryQuantity.toLocaleString(), detail: 'Food, water & medical units', icon: 'supplies', tone: 'amber', foot: 'Stored inventory totals' },
    { title: 'Network health', value: '94%', detail: 'Simulated node availability', icon: 'network', tone: 'green', foot: 'Demo network status' },
  ]
  return <div className="summary-grid">{cards.map((card) => { const Icon = iconMap[card.icon]; return <article className={`summary-card tone-${card.tone}`} key={card.title}><div className="summary-top"><span>{card.title}</span><span className="summary-icon"><Icon size={17} /></span></div><strong className="summary-value">{card.value}</strong><span className="summary-detail">{card.detail}</span><div className="summary-foot"><i />{card.foot}</div></article> })}</div>
}
