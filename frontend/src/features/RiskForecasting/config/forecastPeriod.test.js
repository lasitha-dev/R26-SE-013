import { describe, it, expect } from 'vitest';
import {
  parsePeriod,
  shiftPeriod,
  isSamePeriod,
  getReferencePeriod,
  getDefaultTargetPeriod,
} from './forecastPeriod';

describe('forecastPeriod config', () => {
  it('parses valid YYYY-MM periods and rejects invalid ones', () => {
    expect(parsePeriod('2024-12')).toEqual({ year: 2024, month: 12 });
    expect(parsePeriod('2024-13')).toBeNull();
    expect(parsePeriod('2024-1')).toBeNull();
    expect(parsePeriod('')).toBeNull();
    expect(parsePeriod(undefined)).toBeNull();
  });

  it('shifts across year boundaries in both directions', () => {
    expect(shiftPeriod({ year: 2024, month: 12 }, 1)).toEqual({ year: 2025, month: 1 });
    expect(shiftPeriod({ year: 2025, month: 1 }, -1)).toEqual({ year: 2024, month: 12 });
    expect(shiftPeriod({ year: 2025, month: 6 }, 0)).toEqual({ year: 2025, month: 6 });
  });

  it('compares periods', () => {
    expect(isSamePeriod({ year: 2025, month: 1 }, { year: 2025, month: 1 })).toBe(true);
    expect(isSamePeriod({ year: 2025, month: 1 }, { year: 2025, month: 2 })).toBe(false);
    expect(isSamePeriod(null, { year: 2025, month: 1 })).toBe(false);
  });

  it('uses the configured reference period when valid', () => {
    const now = new Date(2026, 9, 13);
    expect(getReferencePeriod(now, '2024-12')).toEqual({ year: 2024, month: 12 });
    expect(getDefaultTargetPeriod(now, '2024-12')).toEqual({ year: 2025, month: 1 });
  });

  it('falls back to the calendar month when no valid period is configured', () => {
    const now = new Date(2026, 9, 13); // October 2026
    expect(getReferencePeriod(now, null)).toEqual({ year: 2026, month: 10 });
    expect(getReferencePeriod(now, '')).toEqual({ year: 2026, month: 10 });
    expect(getDefaultTargetPeriod(now, 'not-a-period')).toEqual({ year: 2026, month: 11 });
  });
});
