import { describe, expect, it } from 'vitest'
import {
  AVAILABILITY_MODE_EXPECTED,
  EXPECTED_ACTIVE_API_PROTOCOL_HASH_10A1,
  EXPECTED_ACTIVE_TRANSPORT_PROTOCOL_HASH_10B1A,
  EXPECTED_HISTORICAL_TRANSPORT_PROTOCOL_HASH_10B1,
  LIVE_OPERATIONAL_STATUS_EXPECTED,
  PROTOCOL_CHECK_FAILED,
  RECORD_DOMAIN_SCOPE_EXPECTED,
  RUNTIME_DATA_MODE_EXPECTED,
  evaluateProtocolCompatibility,
  evaluateSnapshotBeginContract,
  evaluateWsParentContract,
  protocolCheckFailureOutcome,
} from '../api/geospatialContract'

function validProtocolResponse(overrides = {}) {
  return {
    active_api_protocol_hash_10a1: EXPECTED_ACTIVE_API_PROTOCOL_HASH_10A1,
    active_transport_protocol_hash_10b1a: EXPECTED_ACTIVE_TRANSPORT_PROTOCOL_HASH_10B1A,
    historical_transport_protocol_hash_10b1: EXPECTED_HISTORICAL_TRANSPORT_PROTOCOL_HASH_10B1,
    runtime_data_mode: RUNTIME_DATA_MODE_EXPECTED,
    live_operational_analysis_status: LIVE_OPERATIONAL_STATUS_EXPECTED,
    availability_mode: 'RETROSPECTIVE_PROXY',
    record_domain_scope: 'HISTORICAL_ONLY',
    ...overrides,
  }
}

describe('11A-CONTRACT-01: active 10B.1a hash accepted', () => {
  it('accepts a fully matching protocol response', () => {
    const result = evaluateProtocolCompatibility(validProtocolResponse())
    expect(result.status).toBe('PROTOCOL_COMPATIBLE')
    expect(result.reasons).toEqual([])
  })
})

describe('11A-CONTRACT-02: wrong active 10B.1a hash -> INCOMPATIBLE_BACKEND_PROTOCOL', () => {
  it('rejects a mismatched active_transport_protocol_hash_10b1a', () => {
    const result = evaluateProtocolCompatibility(
      validProtocolResponse({ active_transport_protocol_hash_10b1a: 'deadbeef'.repeat(8) }),
    )
    expect(result.status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
    expect(result.reasons.some((r) => r.includes('active_transport_protocol_hash_10b1a'))).toBe(true)
  })

  it('rejects a missing protocol response entirely', () => {
    expect(evaluateProtocolCompatibility(null).status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
    expect(evaluateProtocolCompatibility(undefined).status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
  })
})

describe('11A-CONTRACT-03: WS 10B.1 parent identity validated against protocol historical 10B.1', () => {
  it('accepts a WS frame whose active_transport_protocol_hash_10b1 matches /protocol historical_transport_protocol_hash_10b1', () => {
    const protocolResponse = validProtocolResponse()
    const wsFrame = { active_transport_protocol_hash_10b1: EXPECTED_HISTORICAL_TRANSPORT_PROTOCOL_HASH_10B1 }
    const result = evaluateWsParentContract(wsFrame, protocolResponse)
    expect(result.status).toBe('PROTOCOL_COMPATIBLE')
  })

  it('NEVER compares the WS parent field against the active 10B.1a hash', () => {
    // deliberately construct a WS frame whose field equals the ACTIVE
    // 10b1a hash (wrong value for this field) -- must be rejected,
    // proving the comparison target is historical_transport_protocol_hash_10b1,
    // never active_transport_protocol_hash_10b1a.
    const protocolResponse = validProtocolResponse()
    const wsFrame = { active_transport_protocol_hash_10b1: EXPECTED_ACTIVE_TRANSPORT_PROTOCOL_HASH_10B1A }
    const result = evaluateWsParentContract(wsFrame, protocolResponse)
    expect(result.status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
  })

  it('rejects when the WS parent field does not match either historical value', () => {
    const protocolResponse = validProtocolResponse()
    const wsFrame = { active_transport_protocol_hash_10b1: 'bogus' }
    const result = evaluateWsParentContract(wsFrame, protocolResponse)
    expect(result.status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
  })
})

// ---------------------------------------------------------------------
// Checkpoint 11A.1
// ---------------------------------------------------------------------

describe('11A1-CONTRACT-01: wrong availability_mode is rejected', () => {
  it('accepts the exact expected value', () => {
    expect(AVAILABILITY_MODE_EXPECTED).toBe('RETROSPECTIVE_PROXY')
    const result = evaluateProtocolCompatibility(validProtocolResponse({ availability_mode: 'RETROSPECTIVE_PROXY' }))
    expect(result.status).toBe('PROTOCOL_COMPATIBLE')
  })

  it('rejects any other value', () => {
    const result = evaluateProtocolCompatibility(validProtocolResponse({ availability_mode: 'LIVE_OPERATIONAL_FEED' }))
    expect(result.status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
    expect(result.reasons.some((r) => r.includes('availability_mode'))).toBe(true)
  })

  it('rejects a missing availability_mode', () => {
    const response = validProtocolResponse()
    delete response.availability_mode
    expect(evaluateProtocolCompatibility(response).status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
  })
})

describe('11A1-CONTRACT-02: wrong record_domain_scope is rejected', () => {
  it('accepts the exact expected value', () => {
    expect(RECORD_DOMAIN_SCOPE_EXPECTED).toBe('HISTORICAL_ONLY')
    const result = evaluateProtocolCompatibility(validProtocolResponse({ record_domain_scope: 'HISTORICAL_ONLY' }))
    expect(result.status).toBe('PROTOCOL_COMPATIBLE')
  })

  it('rejects any other value', () => {
    const result = evaluateProtocolCompatibility(validProtocolResponse({ record_domain_scope: 'LIVE_AND_HISTORICAL' }))
    expect(result.status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
    expect(result.reasons.some((r) => r.includes('record_domain_scope'))).toBe(true)
  })

  it('rejects a missing record_domain_scope', () => {
    const response = validProtocolResponse()
    delete response.record_domain_scope
    expect(evaluateProtocolCompatibility(response).status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
  })
})

describe('11A1-CONTRACT-03: all seven expected protocol semantics must match simultaneously', () => {
  const FIELDS = [
    'active_api_protocol_hash_10a1',
    'active_transport_protocol_hash_10b1a',
    'historical_transport_protocol_hash_10b1',
    'runtime_data_mode',
    'live_operational_analysis_status',
    'availability_mode',
    'record_domain_scope',
  ]

  it('a fully matching response checks all seven fields and is compatible', () => {
    const result = evaluateProtocolCompatibility(validProtocolResponse())
    expect(result.status).toBe('PROTOCOL_COMPATIBLE')
    expect(result.reasons).toEqual([])
  })

  it.each(FIELDS)('breaking %s alone makes the whole response incompatible', (field) => {
    const result = evaluateProtocolCompatibility(validProtocolResponse({ [field]: 'WRONG_VALUE' }))
    expect(result.status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
    expect(result.reasons.some((r) => r.includes(field))).toBe(true)
  })

  it('breaking every field at once reports all seven mismatches', () => {
    const broken = Object.fromEntries(FIELDS.map((f) => [f, 'WRONG_VALUE']))
    const result = evaluateProtocolCompatibility(validProtocolResponse(broken))
    expect(result.status).toBe('INCOMPATIBLE_BACKEND_PROTOCOL')
    expect(result.reasons).toHaveLength(FIELDS.length)
  })
})

describe('11A1-BEGIN-CONTRACT: snapshot_begin metadata validated independently of transport_ready', () => {
  function validBeginFrame() {
    return {
      active_api_protocol_hash_10a1: EXPECTED_ACTIVE_API_PROTOCOL_HASH_10A1,
      // real backend naming quirk (module docstring): this field, despite
      // its name, is the HISTORICAL 10B.1 parent identity.
      active_transport_protocol_hash_10b1: EXPECTED_HISTORICAL_TRANSPORT_PROTOCOL_HASH_10B1,
      runtime_data_mode: RUNTIME_DATA_MODE_EXPECTED,
      live_operational_analysis_status: LIVE_OPERATIONAL_STATUS_EXPECTED,
    }
  }

  it('accepts a matching snapshot_begin frame', () => {
    const result = evaluateSnapshotBeginContract(validBeginFrame(), validProtocolResponse())
    expect(result.status).toBe('PROTOCOL_COMPATIBLE')
  })

  it('rejects a mismatched active_api_protocol_hash_10a1', () => {
    const result = evaluateSnapshotBeginContract({ ...validBeginFrame(), active_api_protocol_hash_10a1: 'wrong' }, validProtocolResponse())
    expect(result.status).toBe('SNAPSHOT_METADATA_CONTRACT_MISMATCH')
  })

  it('NEVER compares active_transport_protocol_hash_10b1 against the active 10b1a hash', () => {
    const result = evaluateSnapshotBeginContract(
      { ...validBeginFrame(), active_transport_protocol_hash_10b1: EXPECTED_ACTIVE_TRANSPORT_PROTOCOL_HASH_10B1A },
      validProtocolResponse(),
    )
    expect(result.status).toBe('SNAPSHOT_METADATA_CONTRACT_MISMATCH')
  })

  it('rejects a mismatched runtime_data_mode', () => {
    const result = evaluateSnapshotBeginContract({ ...validBeginFrame(), runtime_data_mode: 'LIVE_OPERATIONAL' }, validProtocolResponse())
    expect(result.status).toBe('SNAPSHOT_METADATA_CONTRACT_MISMATCH')
  })

  it('rejects a mismatched live_operational_analysis_status', () => {
    const result = evaluateSnapshotBeginContract({ ...validBeginFrame(), live_operational_analysis_status: 'IMPLEMENTED' }, validProtocolResponse())
    expect(result.status).toBe('SNAPSHOT_METADATA_CONTRACT_MISMATCH')
  })

  it('rejects a missing frame or protocol response', () => {
    expect(evaluateSnapshotBeginContract(null, validProtocolResponse()).status).toBe('SNAPSHOT_METADATA_CONTRACT_MISMATCH')
    expect(evaluateSnapshotBeginContract(validBeginFrame(), null).status).toBe('SNAPSHOT_METADATA_CONTRACT_MISMATCH')
  })
})

describe('11A1-PREFLIGHT-FAILURE: backend-unreachable preflight resolves a structured outcome', () => {
  it('protocolCheckFailureOutcome never throws and returns the same {status, reasons} shape as compatibility checks', () => {
    const outcome = protocolCheckFailureOutcome('network error')
    expect(outcome.status).toBe(PROTOCOL_CHECK_FAILED)
    expect(outcome.reasons).toEqual(['network error'])
  })

  it('falls back to a safe message when no message is given', () => {
    const outcome = protocolCheckFailureOutcome()
    expect(outcome.reasons[0]).toMatch(/geospatial backend/i)
  })
})
