/**
 * Checkpoint 11A Part 4: single API base-configuration boundary.
 *
 * `VITE_GEOSPATIAL_API_BASE_URL` defaults to an empty string, which
 * means "same origin, relative path" -- in local development that
 * relies on the Vite dev-server proxy (`vite.config.js` `server.proxy`)
 * forwarding `/api` to the backend, so no CORS change is ever needed
 * on the locked backend. No production hostname is hardcoded here.
 */

export const GEOSPATIAL_API_BASE_URL = import.meta.env.VITE_GEOSPATIAL_API_BASE_URL || ''

export const GEOSPATIAL_API_PREFIX = `${GEOSPATIAL_API_BASE_URL}/api/geospatial`

/**
 * Derives the WebSocket URL from the configured HTTP origin
 * (http -> ws, https -> wss). When `GEOSPATIAL_API_BASE_URL` is empty
 * (same-origin relative mode), derives from `window.location` instead.
 */
export function geospatialWebSocketUrl() {
  if (GEOSPATIAL_API_BASE_URL) {
    const httpUrl = new URL(`${GEOSPATIAL_API_BASE_URL}/api/geospatial/ws`)
    httpUrl.protocol = httpUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    return httpUrl.toString()
  }
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${wsProtocol}//${window.location.host}/api/geospatial/ws`
}

/**
 * GEO-OWNED-FINAL-08 Section 14: centralizes the one piece of error-body
 * parsing `myAreaApi.js` and `analysisTrendsApi.js` used to each define
 * identically (copy-pasted) -- reads `body.detail.status` if present,
 * `null` for a generic FastAPI error body (`detail` is a bare string or a
 * native-validation array), never guessed. A single shared definition
 * means both clients' structured-vs-generic error distinction can never
 * silently drift apart from each other.
 */
export async function readStructuredErrorStatus(response) {
  try {
    const body = await response.json()
    const status = body?.detail?.status
    return typeof status === 'string' ? status : null
  } catch {
    return null
  }
}
