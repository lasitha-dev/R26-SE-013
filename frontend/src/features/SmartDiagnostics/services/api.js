const API_BASE = import.meta.env.VITE_API_URL || ''

export async function detectImage(file) {
  const url = `${API_BASE}/api/detect`
  const form = new FormData()
  form.append('image', file)

  const res = await fetch(url, { method: 'POST', body: form })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`API error ${res.status}: ${txt}`)
  }
  return res.json()
}

/**
 * Request a Tier 3 LLM clinical reasoning report from the backend.
 *
 * @param {object} detectionResult - The full response from /api/detect.
 * @param {object} [farmMetadata]  - Optional farm context (herd_size, etc.)
 * @returns {Promise<{status: string, reasoning_report: string, model_name: string|null}>}
 */
export async function fetchReasoning(detectionResult, farmMetadata = null) {
  const url = `${API_BASE}/api/reason`

  const body = {
    cattle_detected: detectionResult.cattle_detected,
    detections: detectionResult.detections || [],
    best_detection: detectionResult.best_detection || null,
    disease: detectionResult.disease || null,
    image_size: detectionResult.image_size || null,
    farm_metadata: farmMetadata,
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`Reasoning API error ${res.status}: ${txt}`)
  }

  return res.json()
}

/**
 * Report a new diagnosis case for an animal.
 */
export async function reportDiagnosticCase(payload) {
  const token = localStorage.getItem('token')
  const url = `${API_BASE}/api/vet/cases`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`Failed to report diagnostic case: ${txt}`)
  }
  return res.json()
}

/**
 * Verify a diagnostic case report.
 */
export async function verifyDiagnosticCase(caseId, payload = {}) {
  const token = localStorage.getItem('token')
  const url = `${API_BASE}/api/vet/cases/${caseId}/verify`
  const res = await fetch(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`Failed to verify case: ${txt}`)
  }
  return res.json()
}

/**
 * Fetch diagnostic case history.
 */
export async function fetchDiagnosticCases(params = {}) {
  const token = localStorage.getItem('token')
  const query = new URLSearchParams(params).toString()
  const url = `${API_BASE}/api/vet/cases${query ? `?${query}` : ''}`
  const res = await fetch(url, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`Failed to fetch diagnostic cases: ${txt}`)
  }
  return res.json()
}

/**
 * Delete a diagnostic case record.
 */
export async function deleteDiagnosticCase(caseId) {
  const token = localStorage.getItem('token')
  const url = `${API_BASE}/api/vet/cases/${caseId}`
  const res = await fetch(url, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`Failed to delete diagnostic case: ${txt}`)
  }
  return res.json()
}

