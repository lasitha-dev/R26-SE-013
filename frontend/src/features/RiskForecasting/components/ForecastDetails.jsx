import React from 'react';
import PropTypes from 'prop-types';
import { ForecastSourceBadge } from './ForecastSourceBadge';
import { GlossaryTerm } from './GlossaryTerm';
import { RiskCalculationCard } from './GuideCards';
import { OutlookCard } from './OutlookCard';
import { describeRiskReason, formatProbabilityInterval, isV2Record } from './forecastPresentation';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function Icon({ name, className = '' }) {
  return <span className={`material-symbols-outlined leading-none ${className}`} aria-hidden="true">{name}</span>;
}
Icon.propTypes = { name: PropTypes.string.isRequired, className: PropTypes.string };

function Tile({ icon, label, value, sub }) {
  return (
    <div className="rounded-xl border border-outline-variant/30 bg-surface-container/70 p-3 transition duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg">
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">
        <Icon name={icon} className="text-sm text-primary" />{label}
      </div>
      <div className="text-lg font-extrabold leading-tight text-on-surface">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-on-surface-variant">{sub}</div>}
    </div>
  );
}
Tile.propTypes = { icon: PropTypes.string, label: PropTypes.string, value: PropTypes.node, sub: PropTypes.node };

function Meta({ icon, label, children }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-outline-variant/25 bg-surface-container/50 px-2.5 py-1.5 text-xs">
      <Icon name={icon} className="text-sm text-on-surface-variant" />
      <span className="text-on-surface-variant">{label}</span>
      <span className="font-medium text-on-surface">{children}</span>
    </div>
  );
}
Meta.propTypes = { icon: PropTypes.string, label: PropTypes.string, children: PropTypes.node };

function formatGenerated(iso) {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

/**
 * The technical facts behind a forecast card, laid out as tiles and chips instead of a list.
 * `chance` is the exact figure already formatted by the card.
 */
export function ForecastDetails({ record, district, chance, earlierOutlook, onExplain }) {
  const relative = typeof record.relative_risk === 'number' ? `${record.relative_risk.toFixed(1)}×` : null;
  const interval = formatProbabilityInterval(record);
  const dataPeriod = record.source_year && record.source_month ? `${MONTH_NAMES[record.source_month - 1]} ${record.source_year}` : null;
  const age = typeof record.data_age_months === 'number' ? `${record.data_age_months} ${record.data_age_months === 1 ? 'month' : 'months'} old` : null;
  const generated = formatGenerated(record.generated_at);
  const reason = describeRiskReason(record, district);

  return (
    <details className="group rounded-xl border border-outline-variant/30 bg-surface-container-high/30 transition open:bg-surface-container-high/50">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-primary transition hover:bg-primary/5 [&::-webkit-details-marker]:hidden">
        <span className="inline-flex items-center gap-2"><Icon name="analytics" className="text-lg" />More details</span>
        <Icon name="expand_more" className="text-xl transition-transform duration-300 group-open:rotate-180" />
      </summary>

      <div className="space-y-4 px-4 pb-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Tile icon="target" label="Chance this month" value={chance} sub={interval} />
          {relative && <Tile icon="trending_up" label="Compared with usual" value={relative} sub={`the usual rate for ${district || 'this district'} and month`} />}
          {(dataPeriod || age) && <Tile icon="database" label="Based on data from" value={dataPeriod || 'Not available'} sub={age} />}
        </div>

        {reason ? (
          <div className="flex items-start gap-3 rounded-xl border border-primary/25 bg-primary/5 p-3.5" data-testid="risk-reason">
            <GlossaryTerm
              plain
              label="How this risk was worked out"
              term={<span className="material-symbols-outlined flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/15 text-lg leading-none text-emerald-300" aria-hidden="true">lightbulb</span>}
              align="left"
              prefer="above"
            >
              <RiskCalculationCard reason={reason} />
            </GlossaryTerm>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-white">{reason.headline}</p>
              <p className="text-sm leading-relaxed text-slate-200">{reason.sentence}</p>
              {reason.evidence && <p className="text-xs text-on-surface-variant">{reason.evidence}</p>}
            </div>
          </div>
        ) : !isV2Record(record) && record.predicted_severity ? (
          <p className="rounded-xl border border-primary/25 bg-primary/5 p-3 text-xs text-on-surface">
            Predicted severity: {record.predicted_severity}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Meta icon="verified" label="Source"><ForecastSourceBadge record={record} /></Meta>
          <Meta icon="memory" label="Model"><span className="font-mono text-[11px]">{record.model_variant || 'Standard'}</span></Meta>
          <Meta icon="fiber_manual_record" label="Status"><span className="text-emerald-300">{record.status || 'GENERATED'}</span></Meta>
          {generated && <Meta icon="schedule" label="Issued">{generated}</Meta>}
        </div>

        {earlierOutlook && <OutlookCard compact outlook={earlierOutlook} />}

        {onExplain && (
          <button
            type="button"
            onClick={onExplain}
            className="group/btn flex w-full items-center justify-center gap-2 rounded-xl border border-primary/30 bg-gradient-to-r from-primary/10 to-primary/20 px-4 py-2.5 text-xs font-bold tracking-wide text-primary transition duration-200 hover:-translate-y-0.5 hover:from-primary/20 hover:to-primary/30 hover:shadow-lg"
          >
            <Icon name="psychology" className="text-base transition-transform duration-200 group-hover/btn:scale-110" />
            EXPLAIN FORECAST
            <Icon name="arrow_forward" className="text-base transition-transform duration-200 group-hover/btn:translate-x-1" />
          </button>
        )}
      </div>
    </details>
  );
}

ForecastDetails.propTypes = {
  record: PropTypes.object.isRequired,
  district: PropTypes.string,
  chance: PropTypes.string,
  earlierOutlook: PropTypes.object,
  onExplain: PropTypes.func,
};

