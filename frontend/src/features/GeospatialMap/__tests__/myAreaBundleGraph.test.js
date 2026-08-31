// @vitest-environment node
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import esbuild from 'esbuild'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const FRONTEND_ROOT = join(FEATURE_ROOT, '..', '..', '..')
const ENTRY_POINT = join(FEATURE_ROOT, 'pages', 'MyAreaPage.jsx')

/**
 * GEO-AREA-02H: `MyAreaPage.jsx` is intentionally not yet mounted by
 * `App.jsx` (Page 3 is a later checkpoint), so neither `npm run build`
 * nor Vite's own dev-server module graph ever traverses it, and this
 * suite's other Page-2 tests only `readFileSync` + text-scan source --
 * they never actually import/execute these files, so a wrong import
 * path or a missing named export (e.g. importing a function from a
 * module that never defined it) passes silently. A per-file
 * `esbuild.transformSync` syntax check is equally blind to this, since
 * syntax-checking one file in isolation never resolves what another
 * file actually exports. Only a real `bundle: true` resolution of the
 * whole entry point proves the static module graph is load-bearing.
 */
describe('GEO-AREA-02H-BUNDLE-01: MyAreaPage module graph actually resolves', () => {
  it('bundles the real Page-2 entry point in-memory with esbuild (bundle:true, write:false)', () => {
    const result = esbuild.buildSync({
      entryPoints: [ENTRY_POINT],
      bundle: true,
      write: false,
      platform: 'browser',
      format: 'esm',
      jsx: 'automatic',
      // GEO-MY-AREA-STITCH-16: MyAreaPage now genuinely imports
      // `useDistrictGeometry.js` (the same real district-polygon hook
      // Page 1 already uses), which imports the real district dataset via
      // a Vite `?url` asset reference -- plain esbuild resolves that to
      // its underlying `.geojson` extension (the `?url` suffix is not a
      // loader hint esbuild understands on its own) and has no loader
      // registered for it by default. `'empty'` mirrors the existing
      // `.css` entry: this test proves the module GRAPH resolves, not
      // that raw asset bytes match production Vite's own `?url` handling.
      loader: { '.css': 'empty', '.geojson': 'empty' },
      absWorkingDir: FRONTEND_ROOT,
      logLevel: 'silent',
    })

    expect(result.errors).toEqual([])
    expect(result.outputFiles.length).toBe(1)
    expect(result.outputFiles[0].contents.length).toBeGreaterThan(0)
  })
})
