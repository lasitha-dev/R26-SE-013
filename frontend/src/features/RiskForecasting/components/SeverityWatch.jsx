import React from 'react';
import PropTypes from 'prop-types';
import { WATCH_BADGE_CLASS, describeSeverityWatch } from './forecastPresentation';

/**
 * Severity watch: what the recorded cases and deaths say right now (this month so far and last month).
 * Rule-based and updated from the application's records; it is not a model forecast.
 */
export function SeverityWatch({ recent }) {
  const watch = describeSeverityWatch(recent);
  return (
    <div className="space-y-1" data-testid="severity-watch">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-on-surface-variant">Severity watch (from recorded cases and deaths)</span>
        {watch.level ? (
          <span className={`px-2.5 py-1 rounded-lg border text-xs font-extrabold ${WATCH_BADGE_CLASS[watch.level]}`}>
            {watch.level === 'NONE' ? 'NONE RECORDED' : watch.level}
          </span>
        ) : null}
      </div>
      {watch.lines.map((line) => (
        <p key={line} className="text-xs text-on-surface-variant">{line}</p>
      ))}
      {watch.note && <p className="text-xs text-on-surface-variant">{watch.note}</p>}
      <p className="text-[11px] text-on-surface-variant/80">Rule-based indicator from pilot records; not a model forecast.</p>
    </div>
  );
}

SeverityWatch.propTypes = {
  recent: PropTypes.arrayOf(PropTypes.shape({ label: PropTypes.string, observation: PropTypes.object })),
};
