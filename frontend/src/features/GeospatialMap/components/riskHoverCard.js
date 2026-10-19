/**
 * Risk Zones hover card: what the vet sees when the cursor is on the risk
 * surface (`probeRiskField` in adapters/riskFieldModel.js). Every number is
 * the backend's day-d field at that point; place names are the basemap's own
 * OpenStreetMap places (`nearestMappedPlace`), never invented.
 */
import { BAND_LABEL, BAND_RGBA } from '../adapters/riskFieldModel'

const MAX_CASE_ROWS = 2 // the backend raster carries the top two cases per cell
const TREND_TEXT = { increasing: '▲ Increasing', decreasing: '▼ Decreasing', stable: '● Stable' }
const TREND_COLOUR = { increasing: '#f87171', decreasing: '#4ade80', stable: '#cbd5e1' }

const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
const km = (value) => (value < 1 ? '<1 km' : `${Math.round(value)} km`)
const percent = (share) => (share >= 0.995 ? '100%' : share < 0.01 ? '<1%' : `${Math.round(share * 100)}%`)

/**
 * @param probe     result of `probeRiskField`
 * @param pointPlace nearest mapped place to the cursor ({ name, km }) or null
 * @param district  district name at the cursor or null
 * @param casePlace (coordinates) => nearest mapped place of a case or null
 */
export function riskHoverHtml(probe, { pointPlace = null, district = null, casePlace = () => null } = {}) {
  if (!probe) return ''
  const rgb = `rgb(${BAND_RGBA[probe.band].slice(0, 3).join(',')})`
  const rows = probe.contributing.slice(0, MAX_CASE_ROWS).map((c) => {
    const place = casePlace(c.coordinates)
    const kind = c.recordDomain === 'POSSIBLE' ? 'new outbreak (modelled)' : 'case'
    const label = `${place?.name ? `${escapeHtml(place.name)} ${kind}` : c.recordDomain === 'POSSIBLE' ? 'New outbreak (modelled)' : c.recordDomain === 'HISTORICAL' ? 'Historical record' : 'Verified case'} · ${km(c.km)}`
    return `<div class="geo-risk-hover__case"><span>${label}</span><strong>${percent(c.share)}</strong></div>`
  })
  const more = probe.contributingCount - rows.length
  if (more > 0) rows.push(`<div class="geo-risk-hover__muted">+${more} more case${more === 1 ? '' : 's'}</div>`)
  const near = [pointPlace?.name ? `Near ${escapeHtml(pointPlace.name)}` : null, district ? `${escapeHtml(district)} district` : null].filter(Boolean).join(' · ')
  const trend = probe.trend
    ? `<span style="color:${TREND_COLOUR[probe.trend]}">${TREND_TEXT[probe.trend]}</span> <span class="geo-risk-hover__muted">${probe.delta >= 0 ? '+' : '−'}${Math.abs(probe.delta).toFixed(2)} vs Day ${probe.day - 1}</span>`
    : '<span class="geo-risk-hover__muted">As of the analysis date</span>'
  return [
    `<div class="geo-risk-hover__title" style="color:${rgb}">Relative spatial score · Day ${probe.day}${probe.exploratory ? ' · exploratory' : ''}</div>`,
    `<div class="geo-risk-hover__score"><span class="geo-risk-hover__badge" style="border-color:${rgb};color:${rgb}">${BAND_LABEL[probe.band]}</span><strong>${probe.score.toFixed(2)}</strong></div>`,
    `<div class="geo-risk-hover__row">${trend}</div>`,
    near ? `<div class="geo-risk-hover__row">${near}</div>` : '',
    `<div class="geo-risk-hover__section">Contributing cases: ${probe.contributingCount}</div>`,
    ...rows,
    `<div class="geo-risk-hover__note">Relative score from active cases along their spread paths — not an infection probability.</div>`,
  ].join('')
}
