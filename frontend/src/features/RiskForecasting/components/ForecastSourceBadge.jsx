import React from 'react';
import PropTypes from 'prop-types';
import { describeForecastSource } from './forecastPresentation';

const TONE_CLASSES = Object.freeze({
  backtested: 'bg-emerald-950/80 text-emerald-300 border-emerald-600/40',
  exploratory: 'bg-sky-950/80 text-sky-300 border-sky-600/40',
  baseline: 'bg-slate-800 text-slate-300 border-slate-600/40',
  legacy: 'bg-amber-950/80 text-amber-300 border-amber-600/40',
});

export function ForecastSourceBadge({ record }) {
  const source = describeForecastSource(record);
  if (!source) return <span className="text-slate-600">—</span>;
  return (
    <span
      className={`px-2 py-0.5 rounded text-[10px] font-medium border whitespace-nowrap ${TONE_CLASSES[source.tone]}`}
      title={source.title}
    >
      {source.label}
    </span>
  );
}

ForecastSourceBadge.propTypes = {
  record: PropTypes.object,
};
