const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
