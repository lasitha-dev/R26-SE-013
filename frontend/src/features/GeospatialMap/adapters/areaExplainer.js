/**
 * My Area "AI Explainer": a deterministic, rule-based summary of what this
 * page already shows for the selected day -- the authorised district, the
 * Area Intelligence summary (selected-day raster), the influencing-source
 * cards (backend district influence), the farm list (raster at farm GPS) and
 * the verified case intelligence. No model generates text and nothing is
 * looked up elsewhere; every number and name below comes from those inputs.
 *
 * It never states an infection, a diagnosis, a quarantine or a vaccination
 * decision: modelled risk is called potential exposure, and every action is
 * advisory, labelled with its basis and left to veterinary judgement.
 */
import { formatDisplayDate } from './forecastDate'
import { FARM_LIST_STATUS } from './myAreaFarmList'
import { INFLUENCE_KIND } from './spatialTimelineView'

export const ACTION_BASIS_KIND = Object.freeze({ REPORTS: 'Actual reports', MODEL: 'Model-based monitoring', GUIDANCE: 'Clinical guidance', DATA: 'Data quality' })

const SIGNS = {
  LSD: 'skin nodules, fever or swollen lymph nodes',
  FMD: 'mouth or foot blisters, drooling or lameness',
}
const RISK_WORD = { high: 'HIGH', elevated: 'ELEVATED', moderate: 'MODERATE', low: 'LOW', none: 'NOT COLOURED' }
const EXPLORATORY = 'EXPLORATORY_BEYOND_D7_REACH_HORIZON'

function list(names, max = 3) {
  const shown = names.slice(0, max)
  const more = names.length - shown.length
  if (shown.length === 0) return ''
  const head = shown.length > 1 ? `${shown.slice(0, -1).join(', ')} and ${shown[shown.length - 1]}` : shown[0]
  return more > 0 ? `${shown.join(', ')} and ${more} more` : head
}
const plural = (n, word, many = `${word}s`) => `${n} ${n === 1 ? word : many}`

function sourceName(influence, locationFor) {
  const location = locationFor?.(influence) ?? null
  return location?.place ?? location?.district ?? (influence.recordDomain === 'OPERATIONAL' ? 'a vet-verified case' : 'a historical record')
}

export function buildAreaExplainer({
  districtName = 'Your district', disease = 'LSD', diseaseShortLabel = 'LSD', futureMode = true, timelineOk = false,
  summary = null, influences = [], farmList = null, caseIntel = null, locationFor = null, asOf = null, statusText = null,
  // [{ seedDay, place, local, causePlace }] from the backend new outbreaks.
  newOutbreaks = [],
} = {}) {
  const signs = SIGNS[disease] ?? 'clinical signs of the selected disease'
  const farms = farmList?.rows ?? []
  const byStatus = (status) => farms.filter((f) => f.status === status)
  const verifiedFarms = byStatus(FARM_LIST_STATUS.VERIFIED)
  const affected = byStatus(FARM_LIST_STATUS.AFFECTED)
  const noLocation = byStatus(FARM_LIST_STATUS.NO_LOCATION)
  const herdIssues = farms.filter((f) => f.animalCountStatus === 'INVALID' || f.animalCountStatus === 'MISSING')
  const pending = caseIntel?.pending?.length ?? 0
  const reports = caseIntel?.reportCount ?? 0
  const paragraphs = []
  const actions = []
  const limitations = []

  if (!futureMode) {
    paragraphs.push(reports
      ? `${districtName} has ${plural(reports, `vet-verified ${diseaseShortLabel} report`)} at ${plural(caseIntel?.uniqueFarmCount ?? 0, 'farm')}${pending ? `, and ${plural(pending, 'report')} still pending verification` : ''}. These are recorded reports only; nothing here is predicted.`
      : `No vet-verified ${diseaseShortLabel} report is recorded in ${districtName}. Keep routine surveillance and encourage farmers to report ${signs} early.`)
  } else if (!timelineOk || !summary) {
    paragraphs.push(statusText ?? `The modelled outlook for ${districtName} is not available yet, so only recorded reports can be summarised.`)
  } else {
    const { frame, risk, area } = summary
    const exploratory = frame.horizonStatus === EXPLORATORY
    // 1. District risk summary (selected-day raster in the district).
    paragraphs.push(area && area.coloredKm2 > 0
      ? `On ${formatDisplayDate(frame.date)} (Day ${frame.day}${exploratory ? ', exploratory' : ''}) ${districtName} is ${RISK_WORD[risk?.band] ?? 'NOT COLOURED'}: peak relative score ${risk?.peakScore?.toFixed(2) ?? '—'} (not a probability), with ${Math.round(area.share * 100)}% of the district (${Math.round(area.coloredKm2).toLocaleString('en-US')} km²) on the modelled risk surface.`
      : `On ${formatDisplayDate(frame.date)} (Day ${frame.day}) no part of ${districtName} is on the modelled risk surface.`)

    // 2. Source / model context (influence cards).
    const cards = influences.filter((i) => i.card)
    const local = cards.filter((i) => i.card.kind === INFLUENCE_KIND.LOCAL)
    const external = cards.filter((i) => i.card.kind === INFLUENCE_KIND.APPROACHING)
    if (local.length + external.length === 0) {
      paragraphs.push(`No verified source reaches ${districtName} within the ${frame.count - 1}-day window.`)
    } else {
      const outsideText = external.map((i) => (i.card.influencingToday ? sourceName(i, locationFor) : `${sourceName(i, locationFor)}, from Day ${i.card.firstInfluenceDay}`))
      paragraphs.push(`${plural(local.length + external.length, 'verified source')} ${local.length + external.length === 1 ? 'influences' : 'influence'} the district${local.length ? ` — ${local.length} inside (${list(local.map((i) => sourceName(i, locationFor)))})` : ''}${external.length ? `${local.length ? ' and' : ' —'} ${external.length} outside (${list(outsideText)})` : ''}.`)
    }

    // 3. Potentially affected farms (farm GPS on the selected-day surface).
    paragraphs.push(affected.length
      ? `${plural(affected.length, 'farm')} (${list(affected.map((f) => f.name))}) ${affected.length === 1 ? 'is' : 'are'} potentially affected on this day: plan a monitoring visit and ask farmers to report ${signs}. ${affected.length === 1 ? 'It is' : 'They are'} not infected.`
      : 'No farm without cases is on the risk surface on this day.')
    const verifiedOnSurface = verifiedFarms.filter((f) => f.onSurface)
    if (verifiedOnSurface.length) paragraphs.push(`${list(verifiedOnSurface.map((f) => f.name))} ${verifiedOnSurface.length === 1 ? 'is' : 'are'} also on the surface and already ${verifiedOnSurface.length === 1 ? 'has' : 'have'} verified cases — follow up on those animals.`)
    // New outbreaks in the district (pink): where an existing outbreak's
    // spread first stands in the district, by the selected day.
    const started = newOutbreaks.filter((o) => o.seedDay <= frame.day)
    const upcoming = newOutbreaks.filter((o) => o.seedDay > frame.day).sort((a, b) => a.seedDay - b.seedDay)
    const where = (o) => `${o.place ? `near ${o.place}` : 'in the district'} from Day ${o.seedDay} (${o.local ? 'first move of the local outbreak' : `arriving from ${o.causePlace ?? 'outside the district'}`})`
    if (started.length) paragraphs.push(`${plural(started.length, 'new outbreak')} ${started.length === 1 ? 'is' : 'are'} modelled in ${districtName} by Day ${frame.day}: ${list(started.map(where))}. Each spreads on from the next day — a scenario for planning visits, not a forecast of infection.`)
    else if (upcoming.length) paragraphs.push(`The first new outbreak in ${districtName} is modelled ${where(upcoming[0])}.`)
    paragraphs.push('The map alone does not justify quarantine or vaccinating a specific farm — those need a veterinary authority decision.')

    // Actions (advisory, labelled with their basis).
    const A = []
    const pendingFarms = byStatus(FARM_LIST_STATUS.PENDING)
    if (pendingFarms.length) A.push({ title: 'Check farms on a spread line (pending)', why: `A modelled spread line passes these farms by Day ${frame.day}; examine animals for ${signs}. Pending is not a case.`, basis: ACTION_BASIS_KIND.MODEL, farms: pendingFarms.map((f) => f.name) })
    if (affected.length) A.push({ title: 'Visit potentially affected farms', why: `Their GPS lies on the Day ${frame.day} risk surface; check animals for ${signs}.`, basis: ACTION_BASIS_KIND.MODEL, farms: affected.map((f) => f.name) })
    const approaching = external.filter((i) => !i.card.influencingToday)
    if (approaching.length) A.push({ title: 'Watch sources approaching from outside', why: approaching.map((i) => `${sourceName(i, locationFor)} reaches the district on Day ${i.card.firstInfluenceDay}`).join('; ') + '.', basis: ACTION_BASIS_KIND.MODEL })
    if (area && area.coloredKm2 > 0) A.push({ title: 'Review the coloured parts of the district', why: `${Math.round(area.coloredKm2).toLocaleString('en-US')} km² on the risk surface on Day ${frame.day}${exploratory ? ' (exploratory day — interpret cautiously)' : ''}.`, basis: ACTION_BASIS_KIND.MODEL })
    if (A.length) actions.push({ id: 'A', title: 'Increased monitoring / surveillance', items: A })

    const B = []
    if (verifiedFarms.length) B.push({ title: 'Examine in-contact animals at farms with verified cases', why: `${plural(verifiedFarms.length, 'farm')} with vet-verified ${diseaseShortLabel} reports.`, basis: ACTION_BASIS_KIND.REPORTS, farms: verifiedFarms.map((f) => f.name) })
    B.push({ title: 'Isolation and biosecurity for suspected animals', why: `Consider separating animals with ${signs} and limiting shared equipment while they are assessed.`, basis: ACTION_BASIS_KIND.GUIDANCE })
    actions.push({ id: 'B', title: 'Suspected-case isolation & veterinary assessment', items: B })

    const C = []
    if (reports || local.length) C.push({ title: 'Movement-control assessment', why: `${plural(reports, 'verified report')}${local.length ? ` and ${plural(local.length, 'local source')}` : ''} in ${districtName}. Any restriction needs the competent veterinary authority.`, basis: ACTION_BASIS_KIND.REPORTS })
    C.push({ title: 'Risk zones are not quarantine zones', why: 'A coloured area or a spread path must not be declared a quarantine area on its own.', basis: ACTION_BASIS_KIND.MODEL })
    actions.push({ id: 'C', title: 'Movement control / quarantine consideration', items: C })

    actions.push({ id: 'D', title: 'Vaccination review', items: [{ title: `Review ${diseaseShortLabel} vaccination status with the national programme`, why: 'Follow the national programme and authorised advice; the relative score does not indicate vaccinating a specific farm.', basis: ACTION_BASIS_KIND.GUIDANCE }] })

    // Limitations (scientific uncertainty).
    limitations.push('Relative score, not an infection probability; "potentially affected" means modelled exposure, never infection.')
    limitations.push(`Sources are fixed as of ${formatDisplayDate(asOf)}; new reports count only after vet verification.`)
    if (exploratory) limitations.push('Days 8–14 extend the Day 1–7 reach rate (exploratory).')
    limitations.push('Spread paths stop at the 25 km local domain; wind and cattle density steer direction as labelled extensions, not validated predictors.')
    if (newOutbreaks.length) limitations.push('New outbreaks are modelled where a spread front first stands in the district (its spread then continues from there); they are scenarios, not predicted infections.')
  }

  const E = []
  if (pending) E.push({ title: `Review ${plural(pending, 'pending report')}`, why: 'Pending reports are shown but never used as model sources until verified.', basis: ACTION_BASIS_KIND.REPORTS })
  if (noLocation.length) E.push({ title: 'Update farm locations', why: `${plural(noLocation.length, 'farm')} without valid GPS cannot be evaluated against the risk surface.`, basis: ACTION_BASIS_KIND.DATA, farms: noLocation.map((f) => f.name) })
  if (herdIssues.length) E.push({ title: 'Complete herd sizes', why: `${plural(herdIssues.length, 'farm')} with a missing or invalid animal count.`, basis: ACTION_BASIS_KIND.DATA, farms: herdIssues.map((f) => f.name) })
  E.push({ title: 'Encourage early reporting', why: `Ask farmers to report ${signs} as soon as they appear.`, basis: ACTION_BASIS_KIND.GUIDANCE })
  actions.push({ id: 'E', title: 'Reporting & follow-up', items: E })
  if (noLocation.length) limitations.push(`${plural(noLocation.length, 'farm')} without GPS cannot be evaluated.`)

  return { text: paragraphs.join(' '), paragraphs, actions, limitations }
}
