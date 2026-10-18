/**
 * A short signature of the case records that can be geospatial sources:
 * the selected disease's VERIFIED reports with valid farm GPS, by record
 * key, position and verification time (from the polled `/national-cases`).
 * It changes when a case is verified or withdrawn, a new verified case
 * arrives, or a farm's GPS is added or moved -- so a page can refetch its
 * spatial timeline exactly then (pending and no-GPS reports never change it,
 * because they can never be sources).
 */
export function eligibleSourceSignature(records, disease) {
  if (!disease || !Array.isArray(records)) return ''
  const parts = records
    .filter((r) => r?.disease === disease && r.verification_status === 'VERIFIED' && r.location_status === 'VALID'
      && Number.isFinite(r.latitude) && Number.isFinite(r.longitude))
    .map((r) => `${r.record_key}:${r.latitude.toFixed(5)},${r.longitude.toFixed(5)}:${r.verified_at ?? ''}`)
    .sort()
  // FNV-1a over the joined parts: a compact, stable key.
  let hash = 0x811c9dc5
  const text = parts.join('|')
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return `${parts.length}:${hash.toString(16)}`
}
