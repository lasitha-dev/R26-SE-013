/**
 * GEO-INT-03 Section 6: thin HTTP client for the Geospatial-owned
 * operational endpoint (`GET /api/geospatial/operational-context`,
 * GEO-INT-02). Mirrors `geospatialApi.js`'s conventions (thin wrapper,
 * never computes an operational/scientific value, JSON-parsed
 * passthrough on success) with its own status taxonomy, because this
 * endpoint's contract (401/403/404/409) is materially different from
 * the analysis-route error taxonomy in
 * `semanticLabels.js::ERROR_STATUS_MESSAGES`.
 *
 * Section 2: this route is deliberately NOT globally mounted on this
 * branch yet (GEO-INT-02's own report) -- a real request against it
 * today returns a plain FastAPI 404 with no custom body.
 * `HOST_COMPOSITION_REQUIRED` covers exactly that expected
 * current-branch state.
 *
 * Section 5: no vet_id/email/role is ever sent as a request parameter --
 * authorization is entirely server-side, driven by whatever bearer token
 * the host application's own session already produced. GEO-INT-03H
 * reconciled exactly which real localStorage key that token is stored
 * under -- see `AUTH_TOKEN_STORAGE_KEY`'s own docstring below for the
 * full origin/main evidence trail.
 */

import { GEOSPATIAL_API_PREFIX } from './apiConfig'

export const OPERATIONAL_FETCH_STATUS = {
  SESSION_REQUIRED: 'SESSION_REQUIRED', // 401
  FORBIDDEN: 'FORBIDDEN', // 403
  HOST_COMPOSITION_REQUIRED: 'HOST_COMPOSITION_REQUIRED', // 404 -- route not mounted yet on this branch
  OPERATIONAL_UNAVAILABLE: 'OPERATIONAL_UNAVAILABLE', // 409, or any other non-2xx, or a network failure
  NETWORK_ERROR: 'NETWORK_ERROR', // fetch itself failed (offline, DNS, CORS, etc.)
}

/**
 * GEO-INT-03H: this branch's own frontend has no login feature yet, but
 * the REAL host contract is not a guess -- it was verified exhaustively
 * read-only against `origin/main` (`git grep` across all of
 * `frontend/src`, plus `git show` on the matched files):
 *
 *   - `origin/main:frontend/src/shared_components/VetLogin.jsx` (the
 *     real veterinarian login screen) POSTs to `/api/vet/login` and, on
 *     success, does `localStorage.setItem("token", data.access_token)`
 *     -- the JWT is stored under the bare key `"token"`, nothing else.
 *   - EVERY authenticated request across the entire origin/main frontend
 *     (`shared_components/VetLayout.jsx`, `VetDashboard.jsx`,
 *     `VetSettings.jsx`, `VetAssignedFarms.jsx`,
 *     `VetFarmCattleView.jsx`; `features/SmartDiagnostics/**`;
 *     `features/HealthAnomaly/**`; `context/ProfileContext.jsx`) reads
 *     `localStorage.getItem('token')` and conditionally sends
 *     `Authorization: Bearer ${token}` only when present -- the exact
 *     same conditional-attach shape this module already used.
 *   - Decisively, `origin/main:frontend/src/features/GeospatialMap/
 *     screens/GeospatialMock.jsx` -- a file in THIS SAME feature
 *     directory on origin/main -- calls `GET /api/vet/my-farms` with
 *     `headers: token ? { Authorization: `Bearer ${token}` } : {}`,
 *     `token = localStorage.getItem('token')`. That is this exact
 *     endpoint family's own real precedent, not a guess extrapolated
 *     from an unrelated feature.
 *
 * `role`/`email`/`full_name` are also stored by `VetLogin.jsx`, but are
 * used only for client-side UI display in every file above -- never read
 * by any of them to build an Authorization decision or a request
 * parameter. This module follows that same discipline (Section 4): it
 * reads ONLY the token, never `role`/`email`, and never sends either as
 * a request parameter -- the server alone decides identity/authorization
 * from the verified JWT (`core.security.require_vet_role_claim`,
 * verified read-only in GEO-INT-01/02).
 *
 * Reading this key does NOT create a second authentication system --
 * there is no token issuance, refresh, or validation logic in this
 * module, only a read of the same key `VetLogin.jsx` already writes.
 * When absent, the request is simply sent without an Authorization
 * header, which the server correctly answers with 401 -- the same
 * `SESSION_REQUIRED` state as an expired/invalid token. The token value
 * is never logged and never rendered by any component in this feature
 * (`OperationalStatusChip.jsx`/`OperationalContextPopup.jsx` never
 * receive it at all).
 */
export const AUTH_TOKEN_STORAGE_KEY = 'token'

export function readAuthToken() {
  try {
    return window.localStorage?.getItem(AUTH_TOKEN_STORAGE_KEY) || null
  } catch {
    return null
  }
}

/**
 * GEO-OWNED-FINAL-08 Section 7: "Logout/token disappearance: abort SSE/
 * fetch stream immediately; no background reconnect after logout." This
 * feature has no login/logout code of its own (out of write scope --
 * VetLayout/auth own that), so a live connection cannot be told "the user
 * just logged out" by an event; it can only notice that the token it
 * previously saw is now gone. Pure/testable: both `useOperationalContext.js`
 * (60s poll) and `useVerifiedClinicalEvents.js` (long-lived SSE stream) call
 * this on every tick with the token they connected/last polled with vs. a
 * fresh `readAuthToken()` read, and immediately terminate (abort + surface
 * SESSION_REQUIRED) rather than waiting for the next scheduled attempt to
 * hit a 401. Never reports a disappearance when there was no token to begin
 * with (an already-anonymous session is not a "logout").
 */
export function hasTokenDisappeared(previousToken, currentToken) {
  return Boolean(previousToken) && !currentToken
}

function taggedError(message, operationalStatus) {
  const error = new Error(message)
  error.operationalStatus = operationalStatus
  return error
}

/**
 * Section 6: `AbortController`-aware (`options.signal`). Resolves with
 * the parsed operational-context body on 200; otherwise throws an
 * `Error` tagged `.operationalStatus` (one of `OPERATIONAL_FETCH_STATUS`)
 * -- never a raw stack trace or backend exception string. A deliberate
 * abort re-throws the original `AbortError` unchanged so callers can
 * tell "cancelled" apart from "failed".
 */
export async function fetchOperationalContext({ signal } = {}) {
  const token = readAuthToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}

  let response
  try {
    response = await fetch(`${GEOSPATIAL_API_PREFIX}/operational-context`, { headers, signal })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw taggedError('Could not reach the operational context endpoint.', OPERATIONAL_FETCH_STATUS.NETWORK_ERROR)
  }

  if (response.status === 401) {
    throw taggedError('Session required.', OPERATIONAL_FETCH_STATUS.SESSION_REQUIRED)
  }
  if (response.status === 403) {
    throw taggedError('Veterinarian access required.', OPERATIONAL_FETCH_STATUS.FORBIDDEN)
  }
  if (response.status === 404) {
    throw taggedError('Operational context is not connected yet.', OPERATIONAL_FETCH_STATUS.HOST_COMPOSITION_REQUIRED)
  }
  if (response.status === 409) {
    throw taggedError('Operational data source is temporarily unavailable.', OPERATIONAL_FETCH_STATUS.OPERATIONAL_UNAVAILABLE)
  }
  if (!response.ok) {
    throw taggedError('Operational context request failed.', OPERATIONAL_FETCH_STATUS.OPERATIONAL_UNAVAILABLE)
  }

  return response.json()
}
