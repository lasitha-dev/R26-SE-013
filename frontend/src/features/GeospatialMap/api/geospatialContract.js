/**
 * Checkpoint 11A: frontend/backend contract compatibility guards.
 *
 * These are COMPATIBILITY IDENTITIES, not scientific parameters. No
 * model formula (C0, direction, rate, reach) is duplicated here or
 * anywhere in the frontend -- every scientific value is read verbatim
 * from the backend response.
 *
 * IMPORTANT NUANCE (do not "fix" this later without re-reading the
 * Checkpoint 10B.1a/11A backend contract docs):
 *
 *   - `active_transport_protocol_hash_10b1a` (from GET /api/geospatial/protocol)
 *     is the CURRENT active frontend transport contract. The frontend
 *     validates ITSELF against this value.
 *
 *   - WebSocket frames (`transport_ready`, `snapshot_begin`) still
 *     carry a field literally named `active_transport_protocol_hash_10b1`.
 *     Despite the field's own name, this is the HISTORICAL 10B.1
 *     PARENT contract identity, not the newest active one. It must be
 *     validated against `/protocol`'s `historical_transport_protocol_hash_10b1`
 *     field -- NEVER against `EXPECTED_ACTIVE_TRANSPORT_PROTOCOL_HASH_10B1A`.
 *     This is a real backend naming quirk (the WS field name was fixed
 *     before the 10B.1a correction existed), not a frontend bug.
 */

export const EXPECTED_ACTIVE_API_PROTOCOL_HASH_10A1 =
  'e44761319870e9196768599ad88fde237d709c2b17b03f17662ab144bd5634b8'

export const EXPECTED_ACTIVE_TRANSPORT_PROTOCOL_HASH_10B1A =
  '0549339d2d79659048e2d265403507b756b464d454419c28c295d005d8450f0e'

export const EXPECTED_HISTORICAL_TRANSPORT_PROTOCOL_HASH_10B1 =
  '476a7593aafd4011eec840a7ca60cb339302c037f4e00dd7ba11a239ff153a25'

export const RUNTIME_DATA_MODE_EXPECTED = 'HISTORICAL_RETROSPECTIVE_REPLAY'

export const LIVE_OPERATIONAL_STATUS_EXPECTED =
  'NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE'

// Checkpoint 11A.1 Part 1: these are contract COMPATIBILITY guards, not
// scientific parameters -- they describe how the backend's data-mode
// self-declaration must read for the frontend to trust it, never a
// model input.
export const AVAILABILITY_MODE_EXPECTED = 'RETROSPECTIVE_PROXY'
export const RECORD_DOMAIN_SCOPE_EXPECTED = 'HISTORICAL_ONLY'

export const PROTOCOL_COMPATIBLE = 'PROTOCOL_COMPATIBLE'
export const INCOMPATIBLE_BACKEND_PROTOCOL = 'INCOMPATIBLE_BACKEND_PROTOCOL'
export const PROTOCOL_CHECK_FAILED = 'PROTOCOL_CHECK_FAILED'

/**
 * Pure function -- no network call. Turns a failed `fetch()` (e.g.
 * backend unreachable) into the same `{ status, reasons }` shape
 * `evaluateProtocolCompatibility` returns, so callers never need a
 * separate error-shape branch. Checkpoint 11A.1 Part 8.
 */
export function protocolCheckFailureOutcome(message) {
  return { status: PROTOCOL_CHECK_FAILED, reasons: [message || 'Could not reach the geospatial backend.'] }
}

/**
 * Pure function -- no network call. Validates an already-fetched
 * `GET /api/geospatial/protocol` response body against the frozen
 * frontend expectations (Part 5). Returns `{ status, reasons }`;
 * `reasons` is a list of human-readable (never stack-trace-shaped)
 * mismatch descriptions, empty when compatible.
 */
export function evaluateProtocolCompatibility(protocolResponse) {
  const reasons = []

  if (!protocolResponse || typeof protocolResponse !== 'object') {
    return { status: INCOMPATIBLE_BACKEND_PROTOCOL, reasons: ['protocol response missing or malformed'] }
  }

  const checks = [
    ['active_api_protocol_hash_10a1', EXPECTED_ACTIVE_API_PROTOCOL_HASH_10A1],
    ['active_transport_protocol_hash_10b1a', EXPECTED_ACTIVE_TRANSPORT_PROTOCOL_HASH_10B1A],
    ['historical_transport_protocol_hash_10b1', EXPECTED_HISTORICAL_TRANSPORT_PROTOCOL_HASH_10B1],
    ['runtime_data_mode', RUNTIME_DATA_MODE_EXPECTED],
    ['live_operational_analysis_status', LIVE_OPERATIONAL_STATUS_EXPECTED],
    ['availability_mode', AVAILABILITY_MODE_EXPECTED],
    ['record_domain_scope', RECORD_DOMAIN_SCOPE_EXPECTED],
  ]

  for (const [field, expected] of checks) {
    const actual = protocolResponse[field]
    if (actual !== expected) {
      reasons.push(`${field} mismatch (expected ${expected}, got ${actual === undefined ? 'undefined' : actual})`)
    }
  }

  return reasons.length === 0
    ? { status: PROTOCOL_COMPATIBLE, reasons: [] }
    : { status: INCOMPATIBLE_BACKEND_PROTOCOL, reasons }
}

/**
 * Pure function -- validates the WS `transport_ready`/`snapshot_begin`
 * PARENT identity field (`active_transport_protocol_hash_10b1`,
 * despite its name -- see module docstring) against the value already
 * confirmed from `/protocol`'s `historical_transport_protocol_hash_10b1`
 * during preflight. Never compares it against the 10B.1a hash.
 */
export function evaluateWsParentContract(wsFrame, protocolResponse) {
  if (!wsFrame || !protocolResponse) {
    return { status: INCOMPATIBLE_BACKEND_PROTOCOL, reasons: ['missing WS frame or protocol response'] }
  }
  const wsParentHash = wsFrame.active_transport_protocol_hash_10b1
  const expectedParentHash = protocolResponse.historical_transport_protocol_hash_10b1
  if (wsParentHash !== expectedParentHash) {
    return {
      status: INCOMPATIBLE_BACKEND_PROTOCOL,
      reasons: [`WS active_transport_protocol_hash_10b1 (${wsParentHash}) != /protocol historical_transport_protocol_hash_10b1 (${expectedParentHash})`],
    }
  }
  return { status: PROTOCOL_COMPATIBLE, reasons: [] }
}

export const SNAPSHOT_METADATA_CONTRACT_MISMATCH = 'SNAPSHOT_METADATA_CONTRACT_MISMATCH'

/**
 * Checkpoint 11A.1 Part 3: `snapshot_begin` carries its own copy of the
 * scientific/transport identity fields -- it must never be trusted
 * merely because an earlier `transport_ready` frame passed. Pure
 * function, no network call.
 *
 * `snapshot_begin.active_transport_protocol_hash_10b1` carries the SAME
 * naming quirk as the `transport_ready` frame (see module docstring):
 * despite its name it is the HISTORICAL 10B.1 parent identity and is
 * compared against `/protocol`'s `historical_transport_protocol_hash_10b1`,
 * never the active 10b1a hash.
 */
export function evaluateSnapshotBeginContract(beginFrame, protocolResponse) {
  if (!beginFrame || !protocolResponse) {
    return { status: SNAPSHOT_METADATA_CONTRACT_MISMATCH, reasons: ['missing snapshot_begin frame or protocol response'] }
  }
  const checks = [
    ['active_api_protocol_hash_10a1', beginFrame.active_api_protocol_hash_10a1, protocolResponse.active_api_protocol_hash_10a1],
    ['active_transport_protocol_hash_10b1', beginFrame.active_transport_protocol_hash_10b1, protocolResponse.historical_transport_protocol_hash_10b1],
    ['runtime_data_mode', beginFrame.runtime_data_mode, protocolResponse.runtime_data_mode],
    ['live_operational_analysis_status', beginFrame.live_operational_analysis_status, protocolResponse.live_operational_analysis_status],
  ]
  const reasons = []
  for (const [field, actual, expected] of checks) {
    if (actual !== expected) {
      reasons.push(`snapshot_begin.${field} (${actual}) != expected (${expected})`)
    }
  }
  return reasons.length === 0
    ? { status: PROTOCOL_COMPATIBLE, reasons: [] }
    : { status: SNAPSHOT_METADATA_CONTRACT_MISMATCH, reasons }
}
