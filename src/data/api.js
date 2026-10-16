const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    })
  } catch (cause) {
    const reason = cause instanceof Error ? cause.message : String(cause)
    throw new Error(
      `Cannot reach the ResQMesh API at ${API_BASE_URL}${path}: ${reason}. Check backend availability and CORS settings.`,
      { cause },
    )
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') {
        message = body.detail
      } else if (Array.isArray(body.detail)) {
        message = body.detail.map((issue) => {
          const field = Array.isArray(issue.loc) ? issue.loc.slice(1).join('.') : ''
          return field ? `${field}: ${issue.msg}` : issue.msg
        }).join('; ')
      }
    } catch {
      // Keep the HTTP status message when an error response has no JSON body.
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return response.status === 204 ? null : response.json()
}

const json = (method, body) => ({ method, body: JSON.stringify(body) })

export const api = {
  loadDashboard: () => Promise.all([
    request('/incidents'),
    request('/teams'),
    request('/resources'),
  ]),
  createIncident: (incident) => request('/incidents', json('POST', incident)),
  updateIncident: (id, changes) => request(`/incidents/${encodeURIComponent(id)}`, json('PATCH', changes)),
  deleteIncident: (id) => request(`/incidents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  updateTeam: (id, changes) => request(`/teams/${encodeURIComponent(id)}`, json('PATCH', changes)),
  updateResource: (id, changes) => request(`/resources/${encodeURIComponent(id)}`, json('PATCH', changes)),
  assignTeam: (teamId, incidentId) => request(
    `/teams/${encodeURIComponent(teamId)}/assignments`,
    json('POST', { incident_id: incidentId }),
  ),
  loadAgentStatus: () => request('/agents/status'),
  loadAgentRecommendations: () => request('/agents/recommendations'),
  loadIncidentRecommendation: (incidentId) => request(`/agents/incidents/${encodeURIComponent(incidentId)}`),
  loadSyncDashboard: (skip = 0, limit = 50) => request(`/sync/dashboard?skip=${skip}&limit=${limit}`),
  sendSyncNow: () => request('/sync/dashboard/send', { method: 'POST' }),
}
