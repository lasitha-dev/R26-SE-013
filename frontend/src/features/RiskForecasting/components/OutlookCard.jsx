import React from 'react';
import PropTypes from 'prop-types';
import { formatProbabilityInterval } from './forecastPresentation';

export const OUTLOOK_DISCLAIMER =
  'A climatology-based seasonal outlook from historical district-month outbreak frequency. ' +
  'It does not include current surveillance or recent environmental conditions.';
export const OUTLOOK_DISCLAIMER_SI =
  'අතීත සෘතුමය රටාව මත පදනම් වූ අවදානම් දර්ශනයකි. වත්මන් රෝග වාර්තා හෝ මෑත කාලගුණ දත්ත ඇතුළත් නැත.';

function percent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

/** Plain-language evidence line: how many years the pattern is based on. */
export function describeOutlookEvidence(outlook) {
  if (!outlook) return null;
  const { years_observed: years, positive_years: positive } = outlook;
  if (typeof years !== 'number' || typeof positive !== 'number') return null;
  return `Historical evidence: ${years} years, ${positive} with an outbreak in this month.`;
}

/**
 * Seasonal Outlook (next month). Never shows a risk tier: a climatology figure has no "relative risk".
 * `compact` renders only the one-line reminder used beside an early-month forecast.
 */
export function OutlookCard({ outlook, preview = false, compact = false }) {
  if (!outlook) return null;
  const interval = formatProbabilityInterval(outlook);

  if (compact) {
    return (
      <p className="text-xs text-on-surface-variant" data-testid="outlook-compact">
        Outlook issued earlier: {percent(outlook.probability)}{interval ? ` (${interval})` : ''}
      </p>
    );
  }

  return (
    <div
      className="p-4 rounded-xl border border-sky-500/30 bg-sky-500/5 space-y-2"
      data-testid="outlook-card"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="px-2.5 py-1 rounded-md bg-sky-950/80 text-sky-300 border border-sky-600/40 text-xs font-bold tracking-wide">
          SEASONAL OUTLOOK
        </span>
        <span className="text-[11px] text-on-surface-variant">
          {preview ? 'PREVIEW · not yet issued' : `Issued ${outlook.issue_date} · ${outlook.lead_days} days before the month`}
        </span>
      </div>
      <div className="text-2xl font-extrabold text-on-surface">{percent(outlook.probability)}</div>
      {interval && (
        <p className="text-xs text-on-surface-variant" title="Approximate credible interval from shrunk historical counts">
          {interval}
        </p>
      )}
      {describeOutlookEvidence(outlook) && (
        <p className="text-xs text-on-surface-variant">{describeOutlookEvidence(outlook)}</p>
      )}
      <p className="text-[11px] text-on-surface-variant leading-relaxed">{OUTLOOK_DISCLAIMER}</p>
      <p className="text-[11px] text-on-surface-variant/80 leading-relaxed">{OUTLOOK_DISCLAIMER_SI}</p>
    </div>
  );
}

OutlookCard.propTypes = {
  outlook: PropTypes.object,
  preview: PropTypes.bool,
  compact: PropTypes.bool,
};
