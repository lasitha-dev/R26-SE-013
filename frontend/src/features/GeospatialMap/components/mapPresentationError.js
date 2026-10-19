/** A missing tile/glyph is recoverable; it must not remove a working map. */
export function isFatalMapError(error) {
  const message = typeof error === 'string' ? error : error?.message ?? ''
  return /webgl|graphics context.*lost|context_lost|failed to initialize.*(?:map|painter|renderer)/i.test(message)
}

export const MAP_RESOURCE_ERROR_TEXT = 'Some map tiles or labels could not load. Available map layers remain usable.'
export const MAP_RENDER_ERROR_TEXT = 'The interactive map could not initialize. Geographic playback is unavailable; record details and timeline values remain available.'
