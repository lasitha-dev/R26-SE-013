// @vitest-environment node
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import esbuild from 'esbuild'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const FRONTEND_ROOT = join(FEATURE_ROOT, '..', '..', '..')
const ENTRY_POINT = join(FEATURE_ROOT, 'pages', 'AnalysisTrendsPage.jsx')

/**
 * GEO-ANALYSIS-02 Section 41: `AnalysisTrendsPage.jsx` is intentionally
 * not yet mounted by `App.jsx` (Section 57 -- final host composition is
 * a later checkpoint), so neither `npm run build` nor Vite's own
 * dev-server module graph ever traverses it, and this suite's other
 * Page-3 tests only `readFileSync` + text-scan source -- they never
 * actually import/execute these files, so a wrong import path or a
 * missing named export passes silently. Mirrors
 * `myAreaBundleGraph.test.js`'s exact GEO-AREA-02H precedent (that
 * checkpoint's own preflight caught a real cross-module import defect
 * this same class of test is designed to prevent).
 */
describe('GEO-ANALYSIS-02-BUNDLE-01: AnalysisTrendsPage module graph actually resolves', () => {
  it('bundles the real Page-3 entry point in-memory with esbuild (bundle:true, write:false)', () => {
    const result = esbuild.buildSync({
      entryPoints: [ENTRY_POINT],
      bundle: true,
      write: false,
      platform: 'browser',
      format: 'esm',
      jsx: 'automatic',
      loader: { '.css': 'empty' },
      absWorkingDir: FRONTEND_ROOT,
      logLevel: 'silent',
    })

    expect(result.errors).toEqual([])
    expect(result.outputFiles.length).toBe(1)
    expect(result.outputFiles[0].contents.length).toBeGreaterThan(0)
  })
})
