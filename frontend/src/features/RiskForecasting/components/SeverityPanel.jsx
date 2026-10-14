import React from 'react';
import PropTypes from 'prop-types';
import { describeSeverityPanel } from './forecastPresentation';

const LEVELS = ['LOW', 'MEDIUM', 'HIGH'];

const THEME = {
  NONE: { badge: 'border-slate-500/40 bg-slate-800/60 text-slate-300', bar: 'bg-slate-500', glow: '' },
  LOW: { badge: 'border-emerald-500/40 bg-emerald-950/60 text-emerald-300', bar: 'bg-emerald-400', glow: 'shadow-[0_0_12px_rgba(52,211,153,0.55)]' },
  MEDIUM: { badge: 'border-amber-500/40 bg-amber-950/60 text-amber-300', bar: 'bg-amber-400', glow: 'shadow-[0_0_12px_rgba(251,191,36,0.55)]' },
  HIGH: { badge: 'border-red-500/40 bg-red-950/60 text-red-300', bar: 'bg-red-400', glow: 'shadow-[0_0_12px_rgba(248,113,113,0.6)]' },
};

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function Icon({ name, className = '' }) {
  return <span className={`material-symbols-outlined leading-none ${className}`} aria-hidden="true">{name}</span>;
}
Icon.propTypes = { name: PropTypes.string.isRequired, className: PropTypes.string };

const CHIP =
  'inline-flex items-center gap-2 rounded-lg border border-outline-variant/40 bg-surface-container/70 px-2.5 py-1.5 text-xs text-on-surface ' +
  'transition duration-200 hover:-translate-y-0.5 hover:border-primary/50 hover:bg-primary/5 hover:shadow-md';

function RecordedChip({ item }) {
  const none = item.cases === 0 && item.deaths === 0;
  return (
    <div className={CHIP} data-testid="severity-recorded">
      <Icon name="calendar_month" className="text-sm text-primary" />
      <span className="font-medium">{item.label}</span>
      <span className="text-on-surface-variant">&middot;</span>
      {none ? (
        <span className="inline-flex items-center gap-1 text-on-surface-variant">
          <Icon name="check_circle" className="text-sm text-emerald-400" />No cases or deaths
        </span>
      ) : (
        <>
          <span className="inline-flex items-center gap-1"><Icon name="coronavirus" className="text-sm text-amber-300" />{plural(item.cases, 'case')}</span>
          <span className="inline-flex items-center gap-1"><Icon name="heart_broken" className="text-sm text-red-300" />{plural(item.deaths, 'death')}</span>
        </>
      )}
    </div>
  );
}
RecordedChip.propTypes = { item: PropTypes.object.isRequired };

/**
 * One severity level for a forecast card, with the meter, the evidence behind it and an explanation on hover.
 * Follows the recorded cases and deaths when there are any, otherwise the district's past outbreaks.
 */
export function SeverityPanel({ recent, entry }) {
  const panel = describeSeverityPanel({ recent, entry });
  if (!panel) return null;
  const theme = THEME[panel.level] || THEME.NONE;
  const activeIndex = LEVELS.indexOf(panel.level);

  return (
    <section className="space-y-3 rounded-xl border border-outline-variant/30 bg-surface-container-high/40 p-4" data-testid="severity-panel" aria-label="Severity">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon name="monitor_heart" className="text-lg text-primary" />
          <h4 className="text-sm font-semibold text-on-surface">Severity</h4>
          <span className="group relative inline-flex">
            <button
              type="button"
              aria-label="How is severity decided?"
              className="rounded-full p-0.5 text-on-surface-variant transition hover:text-primary focus:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
            >
              <Icon name="info" className="text-base" />
            </button>
            <span
              role="tooltip"
              className="pointer-events-none absolute left-1/2 top-full z-30 mt-2 w-72 -translate-x-1/2 translate-y-1 rounded-xl border border-outline-variant/50 bg-surface-container-highest p-3 text-left text-xs text-on-surface opacity-0 shadow-2xl transition duration-200 group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100"
            >
              <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-wider text-primary">How this is decided</span>
              <span className="block space-y-1.5 text-on-surface-variant">
                <span className="block">&bull; Cases and deaths recorded in the application are used first (one death counts as much as ten cases).</span>
                <span className="block">&bull; If none are recorded, the district&apos;s past outbreaks are used.</span>
                <span className="block">&bull; It is an early-warning indicator, not a prediction of future severity.</span>
                {panel.historyCounts && <span className="block text-on-surface">Past outbreaks here: {panel.historyCounts}</span>}
              </span>
            </span>
          </span>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-extrabold tracking-wide ${theme.badge}`}
          data-testid="severity-level"
        >
          <span className="h-2 w-2 animate-pulse rounded-full bg-current motion-reduce:animate-none" aria-hidden="true" />
          {panel.level === 'NONE' ? 'NONE RECORDED' : panel.level}
        </span>
      </div>

      <div>
        <div className="grid grid-cols-3 gap-1.5" role="img" aria-label={`Severity ${panel.level}`}>
          {LEVELS.map((level, index) => {
            const active = index <= activeIndex && panel.level !== 'NONE';
            return (
              <div
                key={level}
                className={`h-2 rounded-full transition-all duration-500 ${active ? `${theme.bar} ${index === activeIndex ? theme.glow : ''}` : 'bg-slate-700/60'}`}
              />
            );
          })}
        </div>
        <div className="mt-1 grid grid-cols-3 text-[10px] font-medium uppercase tracking-wider text-on-surface-variant">
          <span>Low</span><span className="text-center">Medium</span><span className="text-right">High</span>
        </div>
      </div>

      <p className="text-xs text-on-surface-variant">{panel.basisText}</p>

      <div className="flex flex-wrap gap-2">
        {panel.items.map((item) => <RecordedChip key={item.label} item={item} />)}
        {panel.items.length === 0 && panel.noReports && (
          <div className="inline-flex items-center gap-2 rounded-lg border border-outline-variant/40 bg-surface-container/70 px-2.5 py-1.5 text-xs text-on-surface-variant">
            <Icon name="cloud_off" className="text-sm" />{panel.noReports}
          </div>
        )}
        {panel.historyLine && (
          <div className={CHIP} data-testid="severity-history">
            <Icon name="history" className="text-sm text-primary" />{panel.historyLine}
          </div>
        )}
      </div>
    </section>
  );
}

/** One-word form for tables: the same level as the panel, with the basis in its tooltip. */
export function SeverityBadge({ recent, entry }) {
  const panel = describeSeverityPanel({ recent, entry });
  if (!panel) return <span className="text-slate-500">&mdash;</span>;
  const theme = THEME[panel.level] || THEME.NONE;
  const facts = (panel.items || []).map((i) => `${i.label}: ${i.text}`).join('; ');
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold ${theme.badge}`}
      title={[panel.basisText, facts, panel.historyLine].filter(Boolean).join(' ')}
      data-testid="severity-badge"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {panel.level === 'NONE' ? 'NONE' : panel.level}
    </span>
  );
}

SeverityBadge.propTypes = {
  recent: PropTypes.array,
  entry: PropTypes.object,
};

SeverityPanel.propTypes = {
  recent: PropTypes.array,
  entry: PropTypes.object,
};
