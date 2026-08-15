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
