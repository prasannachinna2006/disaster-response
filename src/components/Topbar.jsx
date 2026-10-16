import { Bell, ChevronDown, Radio, Shield, WifiOff } from 'lucide-react'

export default function Topbar({ onNotify }) {
  return (
    <header className="topbar">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true"><span /><span /><span /><span /></div>
        <div className="brand-copy"><strong>ResQMesh <span>AI</span></strong><small>Disaster response coordination</small></div>
      </div>
      <div className="topbar-right">
        <div className="demo-pill"><WifiOff size={14} /><span>LOCAL DATA</span><i />Map & network simulated</div>
        <div className="topbar-metric"><div className="metric-icon"><Radio size={16} /></div><div><strong>12 nodes</strong><small><span className="live-dot" /> Simulated</small></div></div>
        <div className="topbar-divider" />
        <button className="icon-button notification-button" aria-label="Notifications" type="button" onClick={onNotify}><Bell size={18} /><i /></button>
        <div className="topbar-role"><div className="user-avatar top-avatar">FR</div><div><strong>Field Responder</strong><small><Shield size={11} /> Response team</small></div><ChevronDown size={15} /></div>
      </div>
    </header>
  )
}
