import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { readStructuredErrorStatus } from '../api/apiConfig'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

function mockResponse(body) {
  return { json: () => Promise.resolve(body) }
}

describe('GEO-OWNED-FINAL-08-API-03: readStructuredErrorStatus (Section 14 centralization)', () => {
  it('reads a structured status string from body.detail.status', async () => {
    await expect(readStructuredErrorStatus(mockResponse({ detail: { status: 'ORIGIN_NOT_FOUND' } }))).resolves.toBe('ORIGIN_NOT_FOUND')
  })

  it('returns null for a generic FastAPI error body (detail is a bare string)', async () => {
    await expect(readStructuredErrorStatus(mockResponse({ detail: 'Not Found' }))).resolves.toBeNull()
  })

  it('returns null for a native FastAPI validation error body (detail is an array)', async () => {
    await expect(readStructuredErrorStatus(mockResponse({ detail: [{ msg: 'field required' }] }))).resolves.toBeNull()
  })

  it('returns null (never throws) when the response body is not valid JSON', async () => {
    const response = { json: () => Promise.reject(new SyntaxError('Unexpected token')) }
    await expect(readStructuredErrorStatus(response)).resolves.toBeNull()
  })
})

describe('GEO-OWNED-FINAL-08-API-04: myAreaApi.js and analysisTrendsApi.js share one implementation, never a second copy', () => {
  const myAreaSrc = readFileSync(join(FEATURE_ROOT, 'api', 'myAreaApi.js'), 'utf-8')
  const analysisTrendsSrc = readFileSync(join(FEATURE_ROOT, 'api', 'analysisTrendsApi.js'), 'utf-8')

  it('myAreaApi.js imports the shared helper from apiConfig.js, never redeclares it', () => {
    expect(myAreaSrc).toContain("import { GEOSPATIAL_API_PREFIX, readStructuredErrorStatus } from './apiConfig'")
    expect(myAreaSrc).not.toMatch(/async function readStructuredErrorStatus/)
  })

  it('analysisTrendsApi.js imports the shared helper from apiConfig.js, never redeclares it', () => {
    expect(analysisTrendsSrc).toContain("import { GEOSPATIAL_API_PREFIX, readStructuredErrorStatus } from './apiConfig'")
    expect(analysisTrendsSrc).not.toMatch(/async function readStructuredErrorStatus/)
  })
})
