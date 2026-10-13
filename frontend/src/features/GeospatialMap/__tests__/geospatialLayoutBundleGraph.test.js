// @vitest-environment node
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import esbuild from 'esbuild'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const FRONTEND_ROOT = join(FEATURE_ROOT, '..', '..', '..')
const ENTRY_POINT = join(FEATURE_ROOT, 'GeospatialLayout.jsx')

/**
 * GEO-OWNED-HOST-WRAPPER-16D: proves `GeospatialLayout.jsx`'s own module
 * graph actually resolves (its relative import of `GeospatialProvider`
 * is a real, correctly-spelled export -- a text-scan test alone can't
 * catch a wrong path or a missing export), mirroring
 * `myAreaBundleGraph.test.js`'s reasoning for Page 2.
 *
 * `react-router-dom` is marked `external`: this branch is an
 * intentionally standalone dev/demo scaffold with no router installed
 * (see `context/useGeospatialUrlSync.js`'s docstring -- the SAME reason
 * every other file in this feature avoids importing it directly).
 * `GeospatialLayout.jsx` is the one file that legitimately needs it,
 * because it is only ever meant to run inside the real host app
 * (`origin/main`), which already depends on `react-router-dom` (see
 * `shared_components/VetLayout.jsx`) -- `external` here reproduces
 * exactly that host-provided-dependency situation rather than papering
 * over a real missing import.
 */
describe('GEO-OWNED-HOST-WRAPPER-16D-BUNDLE-01: GeospatialLayout module graph actually resolves', () => {
  it('bundles GeospatialLayout.jsx in-memory with esbuild (bundle:true, write:false, react-router-dom external)', () => {
    const result = esbuild.buildSync({
      entryPoints: [ENTRY_POINT],
      bundle: true,
      write: false,
      platform: 'browser',
      format: 'esm',
      jsx: 'automatic',
      external: ['react', 'react-dom', 'react-router-dom'],
      loader: { '.css': 'empty' },
      absWorkingDir: FRONTEND_ROOT,
      logLevel: 'silent',
    })

    expect(result.errors).toEqual([])
    expect(result.outputFiles.length).toBe(1)
    expect(result.outputFiles[0].contents.length).toBeGreaterThan(0)
  })
})
