/** Display clipping only: keep the backend line's land segments, with no
 * connection across excluded water or polygon holes. */
const EPS = 1e-10
const cache = new WeakMap()
const cross = (a, b) => a[0] * b[1] - a[1] * b[0]
const sub = (a, b) => [a[0] - b[0], a[1] - b[1]]
const same = (a, b) => Math.abs(a[0] - b[0]) < EPS && Math.abs(a[1] - b[1]) < EPS
const at = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]

function polygonsOf(value) {
  if (value?.type === 'FeatureCollection') return (value.features ?? []).flatMap(polygonsOf)
  const geometry = value?.type === 'Feature' ? value.geometry : value
  return geometry?.type === 'Polygon' ? [geometry.coordinates] : geometry?.type === 'MultiPolygon' ? geometry.coordinates : []
}

function domainOf(domain) {
  if (!domain || typeof domain !== 'object') return { polygons: [], edges: [] }
  if (cache.has(domain)) return cache.get(domain)
  const polygons = polygonsOf(domain), edges = []
  for (const rings of polygons) for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) if (!same(ring[j], ring[i])) edges.push([ring[j], ring[i]])
  }
  const result = { polygons, edges }
  cache.set(domain, result)
  return result
}

function inRing(point, ring) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[j], b = ring[i]
    if (Math.abs(cross(sub(point, a), sub(b, a))) < EPS
      && point[0] >= Math.min(a[0], b[0]) - EPS && point[0] <= Math.max(a[0], b[0]) + EPS
      && point[1] >= Math.min(a[1], b[1]) - EPS && point[1] <= Math.max(a[1], b[1]) + EPS) return true
    if ((a[1] > point[1]) !== (b[1] > point[1]) && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside
  }
  return inside
}

function inDomain(point, polygons) {
  return polygons.some((rings) => rings.length && inRing(point, rings[0]) && !rings.slice(1).some((hole) => inRing(point, hole)))
}

function cutsFor(a, b, edges) {
  const direction = sub(b, a), cuts = [0, 1]
  const axis = Math.abs(direction[0]) >= Math.abs(direction[1]) ? 0 : 1
  if (Math.abs(direction[axis]) < EPS) return cuts
  for (const [c, d] of edges) {
    if (Math.max(a[0], b[0]) + EPS < Math.min(c[0], d[0]) || Math.min(a[0], b[0]) - EPS > Math.max(c[0], d[0])
      || Math.max(a[1], b[1]) + EPS < Math.min(c[1], d[1]) || Math.min(a[1], b[1]) - EPS > Math.max(c[1], d[1])) continue
    const edge = sub(d, c), offset = sub(c, a), denominator = cross(direction, edge)
    if (Math.abs(denominator) < EPS) {
      if (Math.abs(cross(offset, direction)) < EPS) for (const p of [c, d]) {
        const t = (p[axis] - a[axis]) / direction[axis]
        if (t > EPS && t < 1 - EPS) cuts.push(t)
      }
      continue
    }
    const t = cross(offset, edge) / denominator, u = cross(offset, direction) / denominator
    if (t > EPS && t < 1 - EPS && u >= -EPS && u <= 1 + EPS) cuts.push(t)
  }
  return cuts.sort((x, y) => x - y).filter((t, i, values) => i === 0 || t - values[i - 1] > EPS)
}

export function clipLineToDomain(geometry, domain) {
  if (domain === undefined) return geometry // legacy callers without a domain
  const { polygons, edges } = domainOf(domain)
  if (!polygons.length) return null
  const lines = geometry?.type === 'LineString' ? [geometry.coordinates] : geometry?.type === 'MultiLineString' ? geometry.coordinates : []
  const output = []
  for (const line of lines) {
    let piece = null
    for (let i = 1; i < line.length; i += 1) {
      const a = line[i - 1], b = line[i]
      if (![a, b].every((p) => Array.isArray(p) && p.length >= 2 && p.slice(0, 2).every(Number.isFinite))) { piece = null; continue }
      const cuts = cutsFor(a, b, edges)
      for (let k = 1; k < cuts.length; k += 1) {
        if (!inDomain(at(a, b, (cuts[k - 1] + cuts[k]) / 2), polygons)) { piece = null; continue }
        const start = at(a, b, cuts[k - 1]), end = at(a, b, cuts[k])
        if (same(start, end)) continue
        if (piece && same(piece.at(-1), start)) piece.push(end)
        else { piece = [start, end]; output.push(piece) }
      }
    }
  }
  if (!output.length) return null
  const result = output.length === 1 && geometry.type === 'LineString'
    ? { type: 'LineString', coordinates: output[0] }
    : { type: 'MultiLineString', coordinates: output }
  return JSON.stringify(result) === JSON.stringify(geometry) ? geometry : result
}
