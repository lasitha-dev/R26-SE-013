import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const layoutSrc = readFileSync(join(FEATURE_ROOT, 'GeospatialLayout.jsx'), 'utf-8')
// Every safety/behavior assertion below must hold for the actual CODE,
// not for prose in a `/** ... */` doc comment describing intent (e.g.
// the file's own docstring mentions "localStorage" and "/vet/geospatial"
// while explaining that it does NOT use them) -- so those checks run
// against the comment-stripped source.
const layoutCode = layoutSrc.replace(/\/\*[\s\S]*?\*\//g, '')

describe('GEO-OWNED-HOST-WRAPPER-16D-01: wrapper imports and provider wiring', () => {
  it('imports the existing GeospatialProvider rather than defining a new one', () => {
    expect(layoutSrc).toMatch(/import\s*{\s*GeospatialProvider\s*}\s*from\s*'\.\/context\/GeospatialContext'/)
  })

  it('renders GeospatialProvider exactly once, wrapping both the nav and the Outlet', () => {
    const openTags = layoutSrc.match(/<GeospatialProvider>/g) || []
    const closeTags = layoutSrc.match(/<\/GeospatialProvider>/g) || []
    expect(openTags.length).toBe(1)
    expect(closeTags.length).toBe(1)

    const openIndex = layoutCode.indexOf('<GeospatialProvider>')
    const outletIndex = layoutCode.indexOf('<Outlet')
    const closeIndex = layoutCode.indexOf('</GeospatialProvider>')
    expect(openIndex).toBeGreaterThan(-1)
    expect(outletIndex).toBeGreaterThan(openIndex)
    expect(closeIndex).toBeGreaterThan(outletIndex)
  })
})

describe('GEO-OWNED-HOST-WRAPPER-16D-02: exactly three relative local nav destinations', () => {
  it('defines exactly three tab destinations', () => {
    const matches = layoutSrc.match(/{\s*to:\s*'[^']+'/g) || []
    expect(matches.length).toBe(3)
  })

  it('uses the exact relative destinations "." / "my-area" / "analysis"', () => {
    expect(layoutSrc).toContain(`to: '.'`)
    expect(layoutSrc).toContain(`to: 'my-area'`)
    expect(layoutSrc).toContain(`to: 'analysis'`)
  })

  it('never hardcodes the host mount path', () => {
    expect(layoutCode).not.toContain('/vet/geospatial')
    expect(layoutCode).not.toMatch(/to=["']\/vet/)
  })
})

describe('GEO-OWNED-HOST-WRAPPER-16D-03: index tab uses exact/end semantics', () => {
  it('marks only the index ("." ) destination as `end`', () => {
    expect(layoutSrc).toMatch(/{\s*to:\s*'\.',\s*label:\s*'Outbreak Map',\s*end:\s*true\s*}/)
    expect(layoutSrc).toMatch(/{\s*to:\s*'my-area',[^}]*end:\s*false\s*}/)
    expect(layoutSrc).toMatch(/{\s*to:\s*'analysis',[^}]*end:\s*false\s*}/)
  })

  it('passes the per-tab `end` flag through to NavLink', () => {
    expect(layoutSrc).toMatch(/<NavLink[^>]*end=\{tab\.end\}/)
  })
})

describe('GEO-OWNED-HOST-WRAPPER-16D-04: ownership and safety boundaries', () => {
  it('never introduces its own BrowserRouter/Router', () => {
    expect(layoutSrc).not.toMatch(/BrowserRouter|<Router\b|createBrowserRouter/)
  })

  it('never reads localStorage or handles auth tokens', () => {
    expect(layoutCode).not.toMatch(/localStorage/)
    expect(layoutCode).not.toMatch(/Authorization|Bearer\s|jwt/i)
  })

  it('never fetches data itself', () => {
    expect(layoutCode).not.toMatch(/\bfetch\(|axios/)
  })

  it('never mutates the MapLibre camera', () => {
    expect(layoutCode).not.toMatch(/fitBounds|flyTo|easeTo/)
  })

  it('never resets shared selection state', () => {
    expect(layoutCode).not.toMatch(/selectDisease|selectOutbreak|selectArea|clearOutbreakSelection/)
  })

  it('imports nothing from another team feature module', () => {
    expect(layoutCode).not.toMatch(/from\s*['"].*\/(SmartDiagnostics|HealthAnomaly|RiskForecasting)\//)
  })

  it('imports nothing from shared_components', () => {
    expect(layoutCode).not.toMatch(/shared_components/)
  })

  it('introduces no global CSS import', () => {
    expect(layoutCode).not.toMatch(/\.css['"]/)
  })
})
