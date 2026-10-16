import { Crosshair, Info, MapPin } from 'lucide-react'

const mapPins = [
  { type: 'incident', left: '28%', top: '36%', label: 'Building collapse · P1' },
  { type: 'incident warning', left: '61%', top: '25%', label: 'Flooding · P2' },
  { type: 'incident', left: '76%', top: '62%', label: 'Medical · P1' },
  { type: 'team', left: '46%', top: '54%', label: 'Response team' },
  { type: 'team', left: '20%', top: '70%', label: 'Response team' },
  { type: 'shelter', left: '68%', top: '79%', label: 'Community shelter' },
  { type: 'blocked', left: '52%', top: '35%', label: 'Road blocked' },
]

export default function MapPanel({ full = false }) {
  return (
    <section className={`panel map-panel ${full ? 'map-full' : ''}`}>
      <div className="panel-heading"><div><h2>Disaster map</h2><p>Demo incident and resource locations · Sector 4</p></div><span className="map-demo-label"><Info size={13} /> DEMO MAP</span></div>
      <div className="map-canvas" role="img" aria-label="Illustrative demo map showing incident, response team, shelter, and blocked-road markers">
        <div className="map-grid" />
        <div className="map-water water-one" /><div className="map-water water-two" />
        <div className="map-road road-one" /><div className="map-road road-two" /><div className="map-road road-three" /><div className="map-road road-four" />
        <span className="map-place place-one">NORTH RIVERSIDE</span><span className="map-place place-two">CENTRAL DISTRICT</span><span className="map-place place-three">EAST INDUSTRIAL</span><span className="map-place place-four">HARBOR</span>
        {mapPins.map((pin, index) => <span key={`${pin.type}-${index}`} className={`map-pin pin-${pin.type.replace(' ', '-')}`} style={{ left: pin.left, top: pin.top }} title={pin.label}>{pin.type === 'team' ? <span className="pin-team-inner" /> : pin.type === 'shelter' ? <span className="pin-house">⌂</span> : pin.type === 'blocked' ? <span className="pin-x">×</span> : <span className="pin-core" />}</span>)}
        <div className="map-coordinates"><Crosshair size={12} /> 19.0768° N &nbsp; 72.8782° E</div>
      </div>
      <div className="map-footer"><div className="map-legend"><span><i className="legend-dot legend-incident" />Incident</span><span><i className="legend-dot legend-team" />Rescue team</span><span><i className="legend-dot legend-shelter" />Shelter</span><span><i className="legend-dot legend-blocked" />Blocked road</span></div><span className="map-disclaimer"><MapPin size={12} /> Illustrative locations · No live GPS</span></div>
      <p className="map-note">Schematic demo map — not for navigation. A future tile-based map may require an internet connection; offline cached maps are not included in Phase 1.</p>
    </section>
  )
}
