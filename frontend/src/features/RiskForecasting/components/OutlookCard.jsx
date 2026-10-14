import React from 'react';
import PropTypes from 'prop-types';
import { formatChance, formatLikelyRange, monthName } from './forecastPresentation';
import { SeverityPanel } from './SeverityPanel';

export const OUTLOOK_NOTE =
  "Based on past years only. It does not include this year's cases or weather. An updated forecast follows at the start of the month.";

/** "An outbreak was recorded in this month in 0 of the last 7 years." */
export function describeOutlookEvidence(outlook) {
  if (!outlook) return null;
  const { years_observed: years, positive_years: positive } = outlook;
  if (typeof years !== 'number' || typeof positive !== 'number') return null;
  return `An outbreak was recorded in this month in ${positive} of the last ${years} years.`;
}

/**
 * Next-month outlook in ordinary words: the chance, the likely range and how often it happened before.
 * Never shows a risk tier. `compact` is the one-line reminder used inside "More details".
 */
export function OutlookCard({ outlook, preview = false, compact = false, title, severityEntry = null }) {
  if (!outlook) return null;
  const chance = formatChance(outlook.probability);
  const range = formatLikelyRange(outlook);

  if (compact) {
    return (
      <p className="text-xs text-on-surface-variant" data-testid="outlook-compact">
        Outlook given earlier: {chance}{range ? ` (${range})` : ''}
      </p>
    );
  }

  return (
    <div className="p-4 rounded-xl border border-sky-500/30 bg-sky-500/5 space-y-1.5" data-testid="outlook-card">
      <div className="flex items-center justify-between gap-2">
        {title && <h4 className="text-sm font-semibold text-on-surface">{title}</h4>}
        {preview && <span className="text-[11px] text-sky-300">Preview</span>}
      </div>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-2xl font-extrabold text-on-surface">{chance}</span>
        {range && <span className="text-xs text-on-surface-variant">{range}</span>}
      </div>
      {describeOutlookEvidence(outlook) && (
        <p className="text-xs text-on-surface-variant">{describeOutlookEvidence(outlook)}</p>
      )}
      <SeverityPanel entry={severityEntry} recent={[]} />
      <span className="sr-only">{monthName(outlook.target_month)}</span>
    </div>
  );
}

OutlookCard.propTypes = {
  outlook: PropTypes.object,
  preview: PropTypes.bool,
  compact: PropTypes.bool,
  title: PropTypes.string,
  severityEntry: PropTypes.object,
};
