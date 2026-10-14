import React from 'react';
import PropTypes from 'prop-types';
import { SEVERITY_BADGE_CLASS, describeSeverityEstimate } from './forecastPresentation';

/**
 * "Severity if an outbreak occurs": the usual severity of this district's past outbreak years.
 * `compact` is the one-word form for tables. Nothing is shown when the district has no recorded outbreak year.
 */
export function SeverityEstimate({ entry, compact = false }) {
  const estimate = describeSeverityEstimate(entry);
  if (!estimate) return compact ? <span className="text-slate-500">&mdash;</span> : null;

  if (compact) {
    return (
      <span
        className={`px-2 py-0.5 rounded border text-[10px] font-bold ${SEVERITY_BADGE_CLASS[estimate.level]}`}
        title={`${estimate.percents.map((p) => `${p.level} ${p.text}`).join(' · ')}. ${estimate.evidence}`}
        data-testid="severity-estimate-compact"
      >
        {estimate.level}
      </span>
    );
  }

  return (
    <div className="space-y-1" data-testid="severity-estimate">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-on-surface-variant">Severity if an outbreak occurs</span>
        <span className={`px-2.5 py-1 rounded-lg border text-xs font-extrabold ${SEVERITY_BADGE_CLASS[estimate.level]}`}>{estimate.level}</span>
      </div>
      <p className="text-xs text-on-surface-variant">
        {estimate.percents.map((p) => `${p.level.charAt(0)}${p.level.slice(1).toLowerCase()} ${p.text}`).join(' · ')}
      </p>
      <p className="text-[11px] text-on-surface-variant/80">{estimate.evidence}</p>
    </div>
  );
}

SeverityEstimate.propTypes = {
  entry: PropTypes.shape({
    typical: PropTypes.string,
    probabilities: PropTypes.object,
    outbreak_years: PropTypes.number,
    years: PropTypes.array,
  }),
  compact: PropTypes.bool,
};
