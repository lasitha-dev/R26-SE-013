/**
 * Forecast period configuration.
 *
 * Forecasts are issued for the month after the reference ("current") month.
 * In normal operation the reference month is today's calendar month. A
 * demonstration can pin it with VITE_FORECAST_REFERENCE_PERIOD=YYYY-MM
 * (e.g. 2024-12 so that the January 2025 records are the active forecast)
 * without hard-coding a period into the pages.
 */

const PERIOD_PATTERN = /^(\d{4})-(\d{2})$/;

export function parsePeriod(value) {
  const match = PERIOD_PATTERN.exec(String(value ?? '').trim());
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (month < 1 || month > 12) return null;
  return { year, month };
}

export function shiftPeriod({ year, month }, offsetMonths) {
  const index = year * 12 + (month - 1) + offsetMonths;
  return { year: Math.floor(index / 12), month: (index % 12) + 1 };
}

export function isSamePeriod(a, b) {
  return Boolean(a && b) && a.year === b.year && a.month === b.month;
}

/** The month treated as "current". Pinned by env for demonstrations, otherwise today. */
export function getReferencePeriod(now = new Date(), configured = import.meta.env?.VITE_FORECAST_REFERENCE_PERIOD) {
  return parsePeriod(configured) || { year: now.getFullYear(), month: now.getMonth() + 1 };
}

/** The forecast target period shown by default: the month after the reference month. */
export function getDefaultTargetPeriod(now = new Date(), configured = import.meta.env?.VITE_FORECAST_REFERENCE_PERIOD) {
  return shiftPeriod(getReferencePeriod(now, configured), 1);
}
