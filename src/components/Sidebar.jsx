import { Activity, Bot, Boxes, ChevronLeft, ClipboardList, LayoutDashboard, Map, Menu, Network, Settings, Users, Wifi } from 'lucide-react'

const navigation = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'incidents', label: 'Incidents', icon: ClipboardList },
  { id: 'map', label: 'Disaster Map', icon: Map },
  { id: 'teams', label: 'Rescue Teams', icon: Users },
  { id: 'supplies', label: 'Supplies', icon: Boxes },
  { id: 'agents', label: 'AI Agents', icon: Bot },
  { id: 'network', label: 'Network', icon: Network },
  { id: 'sync', label: 'Sync Status', icon: Wifi },
  { id: 'settings', label: 'Settings', icon: Settings },
]

export default function Sidebar({ activePage, onNavigate, open, onClose, activeIncidentCount }) {
  return (
    <>
      <button className="mobile-menu icon-button" type="button" aria-label={open ? 'Close navigation' : 'Open navigation'} onClick={onClose}>
        {open ? <ChevronLeft size={20} /> : <Menu size={20} />}
      </button>
      {open && <button className="sidebar-scrim" aria-label="Close navigation" onClick={onClose} />}
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="sidebar-label">OPERATIONS</div>
        <nav aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${activePage === id ? 'nav-active' : ''}`} type="button" onClick={() => onNavigate(id)}>
              <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
              {id === 'incidents' && <span className="nav-count">{activeIncidentCount}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-incident"><span className="live-dot" /><div><strong>Response active</strong><small>Demo operations · Sector 4</small></div></div>
          <div className="user-card"><div className="user-avatar">FR</div><div><strong>Field Responder</strong><small>Response team</small></div><Activity className="user-activity" size={15} /></div>
        </div>
      </aside>
    </>
  )
}
