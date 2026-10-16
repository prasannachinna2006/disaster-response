import { Droplets, HeartPulse, Package, Users, Utensils } from 'lucide-react'

const iconMap = { food: Utensils, water: Droplets, medical: HeartPulse, teams: Users }
const resourceProgress = (resource) => {
  const referenceQuantity = resource.id === 'RES-FOOD' ? 1720 : resource.id === 'RES-WATER' ? 650 : 190
  return Math.min(100, resource.quantity / referenceQuantity * 100)
}

export default function ResourceStatus({ teams, resources }) {
  const availableTeams = teams.filter((team) => team.status === 'Available').length
  const inventory = resources.map((resource) => ({
    ...resource,
    icon: resource.id === 'RES-FOOD' ? 'food' : resource.id === 'RES-WATER' ? 'water' : 'medical',
    value: resourceProgress(resource),
    quantity: `${resource.quantity} ${resource.unit}`,
  }))
  inventory.push({
    id: 'available-teams',
    name: 'Available teams',
    icon: 'teams',
    value: teams.length ? availableTeams / teams.length * 100 : 0,
    status: teams.length && !availableTeams ? 'Unavailable' : 'Healthy',
    quantity: `${availableTeams} of ${teams.length} teams`,
  })
  return <section className="panel resource-panel"><div className="panel-heading"><div><h2>Resource status</h2><p>Inventory stored in the local database</p></div><button className="panel-link" type="button" onClick={() => window.dispatchEvent(new CustomEvent('resq-navigate', { detail: 'supplies' }))}>All supplies <Package size={14} /></button></div><div className="resource-list">{inventory.map((resource) => { const Icon = iconMap[resource.icon]; const low = resource.status === 'Low stock' || resource.status === 'Unavailable'; return <div className="resource-item" key={resource.id}><div className={`resource-icon ${low ? 'resource-low' : ''}`}><Icon size={16} /></div><div className="resource-body"><div className="resource-label"><strong>{resource.name}</strong><span className={low ? 'text-warning' : ''}>{resource.status}</span></div><div className="resource-progress"><i className={low ? 'progress-low' : ''} style={{ width: `${resource.value}%` }} /></div><small>{resource.quantity}</small></div></div> })}</div></section>
}
