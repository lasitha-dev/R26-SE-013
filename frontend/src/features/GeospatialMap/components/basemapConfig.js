/**
 * Checkpoint 11B Part 3 / GEO26D Section 3: basemap style configuration
 * boundary.
 *
 * Basemap availability is PRESENTATION INFRASTRUCTURE, not scientific-
 * data availability -- the application must remain usable with no
 * remote style configured at all, and a missing/failed basemap must
 * never be confused with `ANALYSIS_UNAVAILABLE` (that status describes
 * the backend's scientific analysis, not map tile availability).
 *
 * No proprietary API key/token is required or hardcoded anywhere in
 * this module.
 *
 * GEO26D: the previous default (a flat single-color background with NO
 * geographic tiles at all) is exactly what an earlier real browser
 * screenshot showed as a blank/white map -- MapLibre itself mounted
 * correctly (controls/attribution rendered) but there was no basemap
 * imagery to paint. `VITE_GEOSPATIAL_BASEMAP_STYLE_URL` was never
 * actually configured anywhere in this repo, so every deployment
 * silently landed on that flat fallback.
 *
 * GEO29A: the GEO26D fix (CARTO Voyager raster tiles,
 * `{s}.basemaps.cartocdn.com/rastertiles/voyager/...`) was ALSO wrong in
 * practice -- a later real browser screenshot showed those exact tile
 * URLs rendering a repeating "API KEY REQUIRED" watermark instead of a
 * basemap (CARTO's anonymous-tile policy is not what was assumed). The
 * OpenStreetMap raster tile server (`tile.openstreetmap.org`) that
 * replaced it was genuinely key-free (verified with a real curl+pixel
 * inspection, not just an HTTP 200) and remains available below
 * (`openRasterDefaultStyle`) for a caller that wants it explicitly, but
 * is a light, colorful, standard-cartography style -- never the "dark
 * desaturated... map stays visually secondary" look GEO31A's basemap
 * section requires for this specific disease-intelligence overlay.
 *
 * GEO31A: switched the default to OpenFreeMap's own public, key-free
 * "dark" vector style (`https://tiles.openfreemap.org/styles/dark`),
 * verified at the time with real curl evidence (style JSON, the
 * `openmaptiles` source's own TileJSON, and one real Sri-Lanka-region
 * `.pbf` tile all independently confirmed 200 with genuine content).
 * That curl evidence proved the REQUESTS succeed -- it did NOT prove the
 * rendered RESULT was readable. GEO33A Section 0's real browser
 * screenshot is the first actual visual evidence of this style, and it
 * showed a map that is "almost entirely black" with land/water/roads/
 * labels not meaningfully distinguishable -- background `rgb(12,12,12)`
 * and water `rgb(27,27,29)` are only 15 RGB levels apart, i.e. this
 * style is a near-monochrome near-black theme, not the "slate/green
 * land, blue-grey water" GEO31A's own text described. Curl-only
 * evidence cannot catch this class of failure (exactly the lesson the
 * GEO29A CARTO watermark taught, repeated here one layer up the stack:
 * a 200 with real bytes is necessary but not sufficient -- the bytes
 * still have to render as something a vet can actually read).
 *
 * GEO33A: the default is now OpenFreeMap's own public, key-free
 * "liberty" vector style (`https://tiles.openfreemap.org/styles/liberty`)
 * -- the checkpoint's own explicit FIRST CHOICE, and OpenFreeMap's
 * flagship, most widely-used style (real labelled roads/coastline/city
 * names, proven legible by its own upstream maintainers against ITS OWN
 * chosen background colors -- unlike a from-scratch recolor this repo
 * would have no way to visually verify without a browser). Style JSON,
 * sprite (`.json`/`.png`), and one real glyph range all re-verified 200
 * via curl before this became the default. The checkpoint explicitly
 * frames further "restrained dark styling" as an OPTIONAL follow-up
 * ("apply ... customization IF NEEDED") gated on real evidence that
 * Liberty's own default isn't enough -- deliberately NOT attempted
 * blind in this round, since a hand-recolored dark derivative built
 * without the ability to see it rendered risks repeating exactly the
 * "looked fine as JSON, unreadable in the browser" failure this style
 * itself was just replaced for. `OPEN_FREE_MAP_DARK_STYLE_URL` stays
 * exported (no longer the default) for reference/opt-in only.
 */

export const BASEMAP_MODE_REMOTE_STYLE = 'REMOTE_STYLE'
export const BASEMAP_MODE_OPEN_RASTER_DEFAULT = 'OPEN_RASTER_DEFAULT'
export const BASEMAP_MODE_OPEN_VECTOR_DARK_DEFAULT = 'OPEN_VECTOR_DARK_DEFAULT'
export const BASEMAP_MODE_OPEN_VECTOR_LIBERTY_DEFAULT = 'OPEN_VECTOR_LIBERTY_DEFAULT'
export const BASEMAP_MODE_NEUTRAL_FALLBACK = 'NEUTRAL_FALLBACK'

// OpenFreeMap's own published style ids -- never a fork/copy of their
// contents into this repo, so upstream fixes/updates apply automatically.
// No API key/token of any kind in either URL.
export const OPEN_FREE_MAP_DARK_STYLE_URL = 'https://tiles.openfreemap.org/styles/dark'
export const OPEN_FREE_MAP_LIBERTY_STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty'

const OSM_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'

/** A minimal, token-free MapLibre style: a single flat background layer
 * and no remote sources. Scientific cell/source/direction layers are
 * added on top of this by `MapLibreCanvas.jsx` regardless of which mode
 * is active -- the basemap only affects the geographic backdrop. */
export function neutralFallbackStyle() {
  return {
    version: 8,
    sources: {},
    layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#eef2f7' } }],
  }
}

/**
 * GEO29A: the real, key-free default basemap -- a raster XYZ tile
 * source (OpenStreetMap's own standard tile server). `{a,b,c}` subdomain
 * rotation is OSM's own documented convention, purely for tile-load
 * parallelism -- carries no credential of any kind.
 */
export function openRasterDefaultStyle() {
  return {
    version: 8,
    sources: {
      osm: {
        type: 'raster',
        tiles: [
          'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
          'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
          'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png',
        ],
        tileSize: 256,
        maxzoom: 19,
        attribution: OSM_ATTRIBUTION,
      },
    },
    layers: [{ id: 'osm-layer', type: 'raster', source: 'osm' }],
  }
}

/**
 * Pure -- reads only the already-resolved env value (never fetches).
 * Returns the style to hand to `new maplibregl.Map({ style })` plus
 * metadata about which mode was selected, for the legend/attribution UI.
 */
export function resolveBasemapConfig(styleUrl) {
  if (typeof styleUrl === 'string' && styleUrl.trim().length > 0) {
    return {
      mode: BASEMAP_MODE_REMOTE_STYLE,
      style: styleUrl,
      // The application does not know a remote style's own attribution
      // text in advance -- MapLibre renders whatever `attribution`
      // control text the style itself declares. This app never
      // suppresses that control.
      note: 'External basemap style configured via VITE_GEOSPATIAL_BASEMAP_STYLE_URL. Network-dependent; availability is not guaranteed and this style is presentation infrastructure only, never scientific evidence.',
    }
  }
  return {
    mode: BASEMAP_MODE_OPEN_VECTOR_LIBERTY_DEFAULT,
    style: OPEN_FREE_MAP_LIBERTY_STYLE_URL,
    // GEO33A Section 0/6: the prior "dark" default proved, in a real
    // browser screenshot, to be too close to black for Sri Lanka
    // geography/roads/labels to read -- Liberty is the checkpoint's own
    // first choice specifically because it is a proven-legible, real
    // labelled style, not a from-scratch dark recolor this repo cannot
    // visually verify.
    note: 'No VITE_GEOSPATIAL_BASEMAP_STYLE_URL configured -- using OpenFreeMap\'s free, key-free "liberty" vector basemap (real roads/coastline/place labels). Network-dependent (tiles will not load offline); this is presentation infrastructure only, never scientific evidence.',
  }
}
