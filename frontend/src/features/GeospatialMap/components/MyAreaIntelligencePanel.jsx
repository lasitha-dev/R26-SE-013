import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'
import { DISTRICT_RISK_NONE } from '../adapters/areaIntelligenceSummary'
import { ACTION_BASIS, FARM_STATUS, FARM_STATUS_LABEL, RELATIVE_TIER_LABEL } from '../adapters/myAreaIntelligence'
import { BAND_RGBA } from '../adapters/riskFieldModel'
import MyAreaFarmList from './MyAreaFarmList'
import { horizonLabel, TIER_ORDER } from '../adapters/spatialTimelineView'
import { AREA_RISK_COLORS } from '../adapters/timelinePresentation'
import { formatVerificationTime } from '../adapters/verificationTime'

const TIER_COLOR = { lower: AREA_RISK_COLORS.green, moderate: AREA_RISK_COLORS.yellow, high: AREA_RISK_COLORS.orange, highest: AREA_RISK_COLORS.red }
const BASIS_CLASS = {
  [ACTION_BASIS.REPORTS]: 'border-rose-300/30 text-rose-200',
  [ACTION_BASIS.MODEL]: 'border-violet-300/30 text-violet-200',
  [ACTION_BASIS.GUIDANCE]: 'border-slate-300/25 text-slate-300',
}
const STATUS_DOT = {
  [FARM_STATUS.REPORTING]: 'bg-[#EF4444]',
  [FARM_STATUS.MONITORED]: 'bg-violet-300',
  [FARM_STATUS.SCORED]: 'bg-slate-300',
  [FARM_STATUS.OUTSIDE]: 'bg-slate-600',
  [FARM_STATUS.NO_GPS]: 'bg-amber-400',
}

function km2(value) {
  return Number.isFinite(value) ? `${Math.round(value).toLocaleString('en-US')} km²` : '—'
}

function Section({ title, badge = null, defaultOpen = true, children }) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-outline-variant/15 bg-surface-container-lowest/25 px-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 py-2.5 text-[10.5px] font-bold uppercase tracking-wide text-on-surface/80 hover:text-on-surface">
        <span>{title}</span>
        <span className="flex items-center gap-1.5">
          {badge !== null && <span className="rounded bg-surface-container-high/70 px-1.5 py-0.5 font-mono text-[9.5px] normal-case tracking-normal text-on-surface">{badge}</span>}
          <span aria-hidden="true" className="material-symbols-outlined text-[14px] transition-transform group-open:rotate-180">expand_more</span>
        </span>
      </summary>
      <div className="pb-3 text-[11px] text-on-surface-variant">{children}</div>
    </details>
  )
}

function Stat({ label, value }) {
  return (
    <div className="flex min-w-0 flex-col justify-between rounded-md border border-outline-variant/15 bg-surface-container/60 px-2 py-1.5">
      <div className="text-[9px] font-semibold uppercase leading-tight tracking-wide text-on-surface-variant/60">{label}</div>
      <div className="mt-0.5 truncate text-base font-bold text-on-surface" title={String(value)}>{value}</div>
    </div>
  )
}

function TierBars({ areas, emptyText = 'No scored land in scope.' }) {
  const total = TIER_ORDER.reduce((sum, t) => sum + (areas?.[t] ?? 0), 0)
  if (!(total > 0)) return <div className="text-[10.5px] text-on-surface-variant/60">{emptyText}</div>
  return (
    <div className="flex flex-col gap-1">
      <div className="flex h-2 overflow-hidden rounded-sm">
        {TIER_ORDER.map((t) => (areas[t] > 0 ? <span key={t} style={{ width: `${(areas[t] / total) * 100}%`, backgroundColor: TIER_COLOR[t] }} title={`${RELATIVE_TIER_LABEL[t]}: ${km2(areas[t])}`} /> : null))}
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px]">
        {[...TIER_ORDER].reverse().map((t) => (
          <span key={t} className="flex items-center justify-between gap-1"><span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ backgroundColor: TIER_COLOR[t] }} />{RELATIVE_TIER_LABEL[t]}</span><span className="font-mono text-on-surface">{km2(areas[t])}</span></span>
        ))}
      </div>
    </div>
  )
}

const RISK_LABEL = { high: 'HIGH', elevated: 'ELEVATED', moderate: 'MODERATE', low: 'LOW', [DISTRICT_RISK_NONE]: 'NONE' }
const riskColour = (band) => (BAND_RGBA[band] ? `rgb(${BAND_RGBA[band].slice(0, 3).join(',')})` : '#94a3b8')

function SummaryRow({ label, value, sub = null, highlight = false, valueStyle = undefined, name }) {
  return (
    <div className={`flex items-start justify-between gap-3 py-2 ${highlight ? '-mx-2 rounded-lg bg-white/[0.04] px-2' : ''}`} data-row={name}>
      <span className="pt-0.5 text-[12px] text-on-surface-variant">{label}</span>
      <span className="text-right">
        <span className={`block text-[13px] font-bold ${highlight ? 'text-amber-300' : 'text-on-surface'}`} style={valueStyle} data-value={name}>{value}</span>
        {sub && <span className="block text-[10px] text-on-surface-variant/60">{sub}</span>}
      </span>
    </div>
  )
}

/** Selected-frame metrics (adapters/areaIntelligenceSummary.js); each row is
 * one kind of quantity: date, score, source count, distance, area, farms. */
function AreaSummaryRows({ summary, diseaseShortLabel, asOf }) {
  const { frame, risk, sources, spread, area, affected, cases } = summary
  const exploratory = frame.horizonStatus === 'EXPLORATORY_BEYOND_D7_REACH_HORIZON'
  return (
    <div className="mt-1 divide-y divide-outline-variant/10" aria-label="Selected day summary">
      <SummaryRow name="active-date" label="Active date" value={<span className="inline-flex items-center gap-2">{formatDisplayDate(frame.date)}<span className="rounded border border-outline-variant/40 px-1.5 py-0.5 font-mono text-[9.5px] text-on-surface-variant">DAY {frame.day}</span></span>} />
      <SummaryRow name="current-frame" label="Current frame" value={`${frame.index + 1} of ${frame.count} · Day ${frame.day}`} sub={frame.day === 0 ? 'as-of date' : exploratory ? 'exploratory extension (Day 8–14)' : 'Day 1–7 reach horizon'} />
      <SummaryRow name="district-risk" label="District risk" value={risk ? RISK_LABEL[risk.band] : '—'} valueStyle={risk ? { color: riskColour(risk.band) } : undefined} />
      <SummaryRow name="peak-score" label="Peak relative score" value={risk?.peakScore !== null && risk?.peakScore !== undefined ? risk.peakScore.toFixed(2) : '—'} />
      <SummaryRow
        name="influencing-origins"
        label="Influencing origins"
        value={sources.local + sources.external}
      />
      <SummaryRow
        name="projected-spread"
        label="Projected spread"
        value={`${spread.activePaths} active path${spread.activePaths === 1 ? '' : 's'}`}
      />
      <SummaryRow name="district-area" label="District area within modelled impact" value={area ? `${Math.round(area.share * 100)}% · ${Math.round(area.coloredKm2).toLocaleString('en-US')} km²` : '—'} />
      <SummaryRow
        name="affected-farms"
        label="Farms that could be affected"
        highlight={Boolean(affected?.farms)}
        value={affected ? `${affected.farms} farm${affected.farms === 1 ? '' : 's'} · ${affected.animals} animals` : '—'}
      />
      <SummaryRow name="verified-cases" label={`Verified ${diseaseShortLabel} cases`} value={`${cases.reports} report${cases.reports === 1 ? '' : 's'} · ${cases.farms} farm${cases.farms === 1 ? '' : 's'}`} sub={cases.pending ? `${cases.pending} pending` : null} />
      <SummaryRow name="focused" label="Focused" value={summary.focused} />
    </div>
  )
}

function FarmButton({ row, focused, onFocus, children }) {
  return (
    <button
      type="button"
      disabled={!row.coordinates}
      onClick={() => onFocus?.(row)}
      aria-pressed={focused}
      title={row.coordinates ? 'Focus this farm on the map' : 'No GPS on record -- cannot be placed on the map'}
      className={`flex w-full items-start gap-2 rounded-md border px-2 py-1.5 text-left transition ${focused ? 'border-primary/50 bg-primary/10' : 'border-outline-variant/15 bg-surface-container-lowest/30 hover:border-primary/30'} disabled:cursor-default`}
    >
      <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[row.status]}`} />
      <span className="min-w-0 flex-1">{children}</span>
    </button>
  )
}

/**
 * Area Intelligence: one panel, every section reading the SAME page state
 * (mode, selected backend frame or observed date, farm roster, cases).
 * Sections collapse; nothing here predicts infections or prescribes measures.
 */
export default function MyAreaIntelligencePanel({
  authorizedDistrict = null,
  // Non-null while the district context is loading/failed/unresolved: the
  // overview shows this text instead of counts (never a placeholder 0).
  contextPendingText = null,
  mode = 'FUTURE_IMPACT',
  diseaseShortLabel = '',
  diseaseCode = null,
  timelineOk = false,
  modelStatusText = null,
  asOf = null,
  activeDate = null,
  activeDay = null,
  horizonStatus = null,
  reachKm = null,
  reachIntervalKm = null,
  outlookRow = null,
  staticTierAreas = null,
  sourceBreakdown = null,
  roster = null,
  caseIntel = null,
  observedThrough = null,
  environment = null,
  environmentObservations = null,
  environmentDate = null,
  environmentUnavailableText = null,
  actions = [],
  focusedFarmId = null,
  onFocusFarm = null,
  onFocusSource = null,
  farmNames = null,
  focusedSource = null,
  // false: the page renders the explanation + actions itself (left column).
  includeNarrative = true,
  // District weather along the timeline (WeatherForecastStrip), optional.
  weatherStrip = null,
  // Selected-frame metrics (buildAreaIntelligenceSummary), Future Impact.
  areaSummary = null,
  // Farms in my district (buildFarmListRows) for the selected day.
  farmList = null,
  // true: the farm list is rendered elsewhere on the page (not in this panel).
  farmsElsewhere = false,
}) {
  const futureMode = mode === 'FUTURE_IMPACT'
  const farms = roster?.rows ?? []
  const reportingFarms = farms.filter((r) => r.status === FARM_STATUS.REPORTING)
  const summary = roster?.summary ?? {}
  return (
    <section className="flex flex-col rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle" aria-label="Area Intelligence">
      <div className="flex items-center justify-between gap-2 border-b border-outline-variant/20 px-3 py-2">
        <div className="text-xs font-semibold text-primary">Area Intelligence</div>
        <div className="rounded border border-outline-variant/25 px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide text-on-surface-variant">{futureMode ? 'Future impact' : 'Verified cases'}</div>
      </div>

      <div className="flex flex-col gap-2 p-2.5">
        <Section title="Authorised district">
          <div className="flex items-center gap-2 text-2xl font-bold text-on-surface"><span className="h-3 w-3 rounded-full border-2 border-[#4ade80]" />{authorizedDistrict ?? (contextPendingText ? '—' : 'Not resolved')}</div>
          {!contextPendingText && areaSummary && (
            <div className="mt-2 flex items-start justify-between gap-2 rounded-lg border border-outline-variant/25 bg-surface-container-lowest/40 px-3 py-2" data-summary="scope">
              <div><div className="text-[9px] font-semibold uppercase tracking-wide text-on-surface-variant/55">Current area</div><div className="font-mono text-[11.5px] font-bold text-on-surface">{authorizedDistrict} district scope</div></div>
              <div className="text-right"><div className="text-[9px] font-semibold uppercase tracking-wide text-on-surface-variant/55">Farm coordinates</div><div className="font-mono text-[11.5px] font-bold text-on-surface" data-value="farm-coordinates">{areaSummary.farms.mapped} of {areaSummary.farms.total} mapped</div></div>
            </div>
          )}
          {futureMode && timelineOk && areaSummary && !contextPendingText ? (
            <AreaSummaryRows summary={areaSummary} diseaseShortLabel={diseaseShortLabel} asOf={asOf} />
          ) : (
            <div className="mt-1 text-[10.5px] leading-snug">
              {contextPendingText ? contextPendingText : futureMode
                ? (timelineOk ? `Day ${activeDay} · ${formatDisplayDate(activeDate)} · ${horizonLabel(horizonStatus)} · relative score fixed as of ${formatDisplayDate(asOf)}` : modelStatusText ?? 'No model frames for this date.')
                : `Observed case history${observedThrough ? ` through ${formatDisplayDate(observedThrough)}` : ''} · real verification dates only`}
            </div>
          )}
        </Section>

        {/* Compact in Future Impact: the summary rows above carry the selected
            day; these sections are details, collapsed until opened. */}
        <Section title="District overview" badge={`${diseaseShortLabel}`} defaultOpen={!(futureMode && areaSummary)}>
          {contextPendingText ? <div className="text-[10.5px] leading-snug" role="status">{contextPendingText}</div> : <>
          <div className="grid grid-cols-3 gap-1.5">
            <Stat label="Verified reports" value={caseIntel?.reportCount ?? 0} />
            <Stat label="Reporting farms" value={caseIntel?.uniqueFarmCount ?? 0} />
            <Stat label="Pending" value={caseIntel?.pending?.length ?? 0} />
            <Stat label="Registered farms" value={summary.total ?? 0} />
            <Stat label="Mapped (GPS)" value={summary.mapped ?? 0} />
            <Stat label="No GPS" value={summary.withoutGps ?? 0} />
          </div>
          <div className="mt-1.5 text-[10px] text-on-surface-variant/60">
            Unique animals: not available (animal identifiers are not exposed to this view).
            {caseIntel?.verifiedWithoutGps?.length ? ` ${caseIntel.verifiedWithoutGps.length} verified report(s) have no farm GPS and are listed, not mapped.` : ''}
          </div>
          </>}
        </Section>

        {farmsElsewhere ? null : farmList ? (
          <MyAreaFarmList districtLabel={authorizedDistrict ?? 'district'} farmList={farmList} futureMode={futureMode && timelineOk} day={activeDay ?? 0} focusedFarmId={focusedFarmId} onFocusFarm={onFocusFarm} />
        ) : (
        <Section title="Registered farms" badge={summary.total ?? 0} defaultOpen={false}>
          {farms.length === 0 ? <div className="text-[10.5px]">No registered farm on record for this district.</div> : (
            <ul className="flex max-h-56 flex-col gap-1 overflow-y-auto pr-0.5">
              {farms.map((row) => (
                <li key={row.farmId}>
                  <FarmButton row={row} focused={row.farmId === focusedFarmId} onFocus={onFocusFarm}>
                    <span className="flex items-center justify-between gap-2"><span className="truncate font-semibold text-on-surface">{row.label}</span>{row.totalAnimals !== null && <span className="shrink-0 text-[9.5px] text-on-surface-variant/60">{row.totalAnimals} animals</span>}</span>
                    <span className="block text-[10px] text-on-surface-variant/65">{FARM_STATUS_LABEL[row.status]}{row.tier ? ` · ${RELATIVE_TIER_LABEL[row.tier]}` : ''}{row.personallyAssigned ? ' · assigned to you' : ''}{row.outsideDistrict ? (row.hasGps ? ' · outside this district' : ' · no district/GPS on record') : ''}</span>
                  </FarmButton>
                </li>
              ))}
            </ul>
          )}
        </Section>
        )}

        {!farmsElsewhere && (
        <Section title="Reporting farms & case history" badge={reportingFarms.length} defaultOpen={!futureMode}>
          {reportingFarms.length === 0 ? <div className="text-[10.5px]">No farm in {authorizedDistrict ?? 'this district'} has a verified {diseaseShortLabel} report.</div> : (
            <ul className="flex flex-col gap-1">
              {reportingFarms.map((row) => (
                <li key={row.farmId}>
                  <FarmButton row={row} focused={row.farmId === focusedFarmId} onFocus={onFocusFarm}>
                    <span className="block truncate font-semibold text-on-surface">{row.label}</span>
                    <span className="block text-[10px] text-on-surface-variant/70">{row.diseaseCaseCount} verified {diseaseShortLabel} report{row.diseaseCaseCount === 1 ? '' : 's'}</span>
                    {row.cases.filter((c) => !diseaseCode || c.disease === diseaseCode).slice(0, 4).map((c) => (
                      <span key={c.caseId} className="block font-mono text-[9.5px] text-on-surface-variant/60">{formatVerificationTime(c.verificationTime) ?? 'Date unavailable'} · verified</span>
                    ))}
                  </FarmButton>
                </li>
              ))}
            </ul>
          )}
          {(caseIntel?.pending?.length ?? 0) > 0 && (
            <div className="mt-1.5 rounded-md border border-amber-400/25 bg-amber-400/[0.06] px-2 py-1.5 text-[10px] text-amber-100/90">
              {caseIntel.pending.length} pending report{caseIntel.pending.length === 1 ? '' : 's'} awaiting vet verification ({caseIntel.pending.map((p) => formatDisplayDate(p.date)).join(', ')}). Shown as hollow amber markers in Verified Cases, never as verified.
            </div>
          )}
        </Section>
        )}

        {futureMode && !areaSummary && (
          <Section title="Selected date" badge={timelineOk ? formatDisplayDate(activeDate) : '—'}>
            {timelineOk && outlookRow ? (
              <div className="flex flex-col gap-1.5">
                <div className="grid grid-cols-3 gap-1.5">
                  <Stat label="Coloured land" value={km2(outlookRow.scoredAreaKm2)} />
                  <Stat label="Farms on coloured land" value={outlookRow.monitoredFarms} />
                  <Stat label="Sources" value={outlookRow.sourceCount} />
                </div>
                <TierBars areas={outlookRow.tierAreas} />
                <div className="text-[10px] leading-snug text-on-surface-variant/60">Areas = land inside this district coloured by the selected day's Risk Zones surface, by band (High, Elevated, Moderate, Low). A coloured area is not an infection status.{outlookRow.exploratory ? ' Days 8–14 extend the Day 1–7 reach formula (exploratory).' : ''}</div>
              </div>
            ) : <div className="text-[10.5px]">No model frame for the selected date.</div>}
          </Section>
        )}

        {weatherStrip && (
        <Section title="Weather & environment" defaultOpen={false}>
          <div className="mb-2">{weatherStrip}</div>
        </Section>
        )}

        {includeNarrative && <MyAreaNarrative {...{ authorizedDistrict, contextPendingText, caseIntel, diseaseShortLabel, futureMode, timelineOk, outlookRow, activeDate, sourceBreakdown, modelStatusText, actions }} />}
      </div>
    </section>
  )
}

/** Area explanation + recommended actions (record-based, advisory). */
export function MyAreaNarrative({ authorizedDistrict, contextPendingText, caseIntel, diseaseShortLabel, futureMode, timelineOk, outlookRow, activeDate, sourceBreakdown, modelStatusText, actions = [] }) {
  return (
    <>
        <Section title="Area explanation" badge="calculated summary">
        {contextPendingText ? <p>{contextPendingText}</p> : <>
          <p className="text-[10.5px] leading-relaxed">{authorizedDistrict ?? 'Your district'} has {caseIntel?.reportCount ?? 0} verified {diseaseShortLabel} reports from {caseIntel?.uniqueFarmCount ?? 0} reporting farms. {caseIntel?.pending?.length ?? 0} reports are pending verification.</p>
          {futureMode && timelineOk && outlookRow ? <p className="mt-1 text-[10.5px] leading-relaxed">On {formatDisplayDate(activeDate)}, the Risk Zones surface colours {km2(outlookRow.scoredAreaKm2)} of the district, with {outlookRow.monitoredFarms} mapped registered farms on that land. Eligible sources: {sourceBreakdown?.inside ?? 0} inside and {sourceBreakdown?.outside ?? 0} outside the district. This is monitoring context, not a forecast of infected farms.</p> : futureMode ? <p className="mt-1 text-[10.5px]">{modelStatusText ?? 'No eligible scientific frame for this date.'}</p> : null}
          <p className="mt-1 text-[9.5px] text-on-surface-variant/60">Record-based explanation; no trained ML or AI inference is used. Advisory actions below retain their reports, model-context or clinical-guidance basis.</p>
        </>}
      </Section>

      <Section title="Recommended veterinary actions" badge="advisory">
        <ul className="flex flex-col gap-1">
          {actions.map((action) => (
            <li key={action.id} className={`rounded-md border px-2 py-1.5 ${action.active ? 'border-teal-300/25 bg-teal-300/[0.05]' : 'border-outline-variant/15 bg-surface-container-lowest/25 opacity-75'}`}>
              <div className="flex items-start justify-between gap-2">
                <span className="text-[11px] font-semibold text-on-surface">{action.title}</span>
                <span className={`shrink-0 rounded border px-1 text-[8.5px] font-semibold uppercase tracking-wide ${BASIS_CLASS[action.basis]}`}>{action.basis}</span>
              </div>
              <div className="text-[10px] leading-snug text-on-surface-variant/70">{action.why}</div>
            </li>
          ))}
        </ul>
        <div className="mt-1.5 text-[9.5px] leading-snug text-on-surface-variant/55">Advisory only. Control measures follow DAPH / provincial procedures and your clinical assessment; nothing here is triggered by relative score or nominal reach alone.</div>
      </Section>
    </>
  )
}
