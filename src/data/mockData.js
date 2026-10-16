export const agents = [
  { name: 'Incident Agent', purpose: 'Classifies and prioritizes incoming incident reports.', status: 'Demo ready', icon: 'scan' },
  { name: 'Rescue Agent', purpose: 'Recommends suitable team-to-task assignments.', status: 'Demo ready', icon: 'users' },
  { name: 'Supply Agent', purpose: 'Highlights food, water, and medicine allocation needs.', status: 'Demo ready', icon: 'package' },
  { name: 'Mapping Agent', purpose: 'Surfaces hazard, shelter, and blocked-road information.', status: 'Demo ready', icon: 'map' },
]

export const nodes = [
  { id: 'Node-001', role: 'Coordination hub', status: 'Connected', pending: 2, signal: 'Strong' },
  { id: 'Node-002', role: 'Field relay', status: 'Connected', pending: 0, signal: 'Good' },
  { id: 'Node-003', role: 'Shelter station', status: 'Sync pending', pending: 7, signal: 'Intermittent' },
]

export const recommendations = [
  { id: 'medical', kind: 'urgent', title: 'Review shelter medical emergency', detail: 'INC-2046 · Harbor Community Shelter', action: 'Review incident', incidentId: 'INC-2046' },
  { id: 'team', kind: 'info', title: 'Assign an available rescue team', detail: '3 teams are currently available for response.', action: 'Review assignment', incidentId: 'INC-2046' },
  { id: 'water', kind: 'warning', title: 'Review low water inventory', detail: '184 cases remaining · Central Market flood zone', action: 'View supplies', target: 'supplies' },
]
