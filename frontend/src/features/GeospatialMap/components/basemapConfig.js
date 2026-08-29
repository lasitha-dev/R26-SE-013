/**
 * Checkpoint 11B Part 3: basemap style configuration boundary.
 *
 * Basemap availability is PRESENTATION INFRASTRUCTURE, not scientific-
 * data availability -- the application must remain usable with no
 * remote style configured at all, and a missing/failed basemap must
 * never be confused with `ANALYSIS_UNAVAILABLE` (that status describes
 * the backend's scientific analysis, not map tile availability).
 *
 * No proprietary API key/token is required or hardcoded anywhere in
 * this module.
 */

export const BASEMAP_MODE_REMOTE_STYLE = 'REMOTE_STYLE'
export const BASEMAP_MODE_NEUTRAL_FALLBACK = 'NEUTRAL_FALLBACK'

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
    mode: BASEMAP_MODE_NEUTRAL_FALLBACK,
    style: neutralFallbackStyle(),
    note: 'No remote basemap style configured -- rendering a neutral, token-free background. Scientific data remains fully inspectable.',
  }
}
