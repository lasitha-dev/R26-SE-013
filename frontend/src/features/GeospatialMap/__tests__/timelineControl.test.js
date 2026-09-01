import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import TimelineControl from '../components/TimelineControl'
import { PAGE1_FORECAST_DATES } from '../adapters/page1ForecastVisualization'

const noop = () => {}

/** Extracts the full opening `<button ...>` tag that carries the given
 * aria-label, regardless of attribute order (React's SSR output orders
 * attributes by JSX declaration order, which does not always put
 * `aria-label` first). */
function buttonTagWithAriaLabel(html, label) {
  const re = new RegExp(`<button[^>]*aria-label="${label}"[^>]*>`)
  const match = html.match(re)
  return match ? match[0] : null
}
const baseProps = {
  t0: '2020-09-28',
  isPlaybackActive: false,
  onSelectDay: noop,
  onPlay: noop,
  onPause: noop,
  onPrev: noop,
  onNext: noop,
  reduceMotion: false,
}

describe('LSD-UI-04: TimelineControl (plan Section 23)', () => {
  it('GEO31A Section 12: a real origin with exactly ONE available frame still renders, as a non-playable snapshot status bar -- never hidden', () => {
    const html = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [0], selectedDay: 0 }))
    expect(html).not.toBe('')
    expect(html).toContain('Forecast risk')
    expect(html).toContain('Origin day')
    expect(html).toContain('28 Sep 2020')
    // No Play/Prev/Next controls for a single, non-playable frame.
    expect(buttonTagWithAriaLabel(html, 'Play')).toBeNull()
  })

  it('GEO-UI-TIMELINE-01 Part 3B/7: a custom datasetLabel replaces the default "Forecast risk" header verbatim', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0], selectedDay: 0, datasetLabel: 'Forecast trajectory' }),
    )
    expect(html).toContain('Forecast trajectory')
    expect(html).not.toContain('Forecast risk')
  })

  it('GEO-UI-TIMELINE-01 Part 3B: the real calendar date is the PRIMARY label -- it appears before the plain-English horizon phrase in document order, both in the single-frame snapshot and in the multi-day header', () => {
    const single = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [0], selectedDay: 0 }))
    expect(single.indexOf('28 Sep 2020')).toBeLessThan(single.indexOf('Origin day'))

    const multi = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2], selectedDay: 1 }),
    )
    // The always-visible header states the real selected date before its
    // own plain-English horizon phrase.
    expect(multi.indexOf('29 Sep 2020')).toBeLessThan(multi.indexOf('1 day after the origin'))
  })

  it('GEO-PAGE1-FINAL: never renders the model-internal D0/D+N horizon notation anywhere -- not in the header, not on any pill, not in a tooltip/title/ARIA label', () => {
    const single = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [0], selectedDay: 0 }))
    const multi = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2, 3, 4, 5, 6, 7], selectedDay: 3 }),
    )
    for (const html of [single, multi]) {
      expect(html).not.toMatch(/\bD\+?\d+\b/)
      expect(html).not.toMatch(/Horizon index/i)
    }
  })

  it('renders nothing when availableDays is empty/undefined', () => {
    expect(renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [], selectedDay: 0 }))).toBe('')
    expect(renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: undefined, selectedDay: 0 }))).toBe('')
  })

  it('GEO-UI-TIMELINE-01: renders nothing (never throws) when t0 is not yet known -- the real pre-outbreak-selection state, since outbreakSelectionReducer\'s own initial state already sets availableForecastFrames to [0] before any origin is selected', () => {
    // Reproduces a real crash found while verifying this checkpoint: with
    // the default [0] frame but no real t0 yet, the previous code called
    // addDaysToIsoDate(undefined, 0), which throws -- and with no error
    // boundary above this route, that unmounted the entire tree
    // (including the host VetLayout sidebar/header). Must render nothing,
    // silently and safely, both for the single-frame and multi-frame shape.
    expect(() =>
      renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, t0: undefined, availableDays: [0], selectedDay: 0 })),
    ).not.toThrow()
    expect(
      renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, t0: undefined, availableDays: [0], selectedDay: 0 })),
    ).toBe('')
    expect(() =>
      renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, t0: null, availableDays: [0, 1, 2], selectedDay: 0 })),
    ).not.toThrow()
    expect(
      renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, t0: null, availableDays: [0, 1, 2], selectedDay: 0 })),
    ).toBe('')
  })

  it('expands once the real multi-day horizon is available, showing every real day up to the REAL last day only (day 7, never a fabricated day 14)', () => {
    const atOrigin = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2, 3, 4, 5, 6, 7], selectedDay: 0 }),
    )
    expect(atOrigin).toContain('Origin day')

    const atLastDay = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2, 3, 4, 5, 6, 7], selectedDay: 7 }),
    )
    expect(atLastDay).toContain('7 days after the origin')
    expect(atLastDay).not.toContain('8 days after the origin')
    expect(atLastDay).not.toContain('14 days after the origin')
  })

  it('shows the real backend-derived actual date for each day, not a hardcoded August/browser date', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: '2020-09-28', availableDays: [0, 1, 2], selectedDay: 0 }),
    )
    // GEO-UI-TIMELINE-01: the always-visible header states the SELECTED
    // day's real date in full (with year); each pill's own primary label
    // is the same real date trimmed to day+month (the header already
    // carries the year for context, so repeating it on every pill in a
    // tight horizontal row would be redundant, not informative) -- still
    // derived from the one real `t0` value, never a second computation.
    expect(html).toContain('28 Sep 2020') // header, origin day (selected)
    expect(html).toContain('28 Sep') // pill, origin day
    expect(html).toContain('29 Sep') // pill, +1 day
    expect(html).toContain('30 Sep') // pill, +2 days -- month has not rolled over here
  })

  it('correctly rolls over a month boundary in the rendered dates', () => {
    // Select day 4 itself so the always-visible header (which states the
    // full year-bearing date of the SELECTED day) is the one exercising
    // the rollover -- the per-pill trimmed label is checked separately.
    const selected = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: '2020-09-28', availableDays: [0, 1, 2, 3, 4], selectedDay: 4 }),
    )
    expect(selected).toContain('2 Oct 2020') // day 4 rolls into October, header (selected)

    const unselected = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: '2020-09-28', availableDays: [0, 1, 2, 3, 4], selectedDay: 0 }),
    )
    expect(unselected).toContain('2 Oct') // day 4 pill, real date still rolls over even when not selected
  })

  it('the play button is disabled at the end of the real range unless already playing', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2], selectedDay: 2, isPlaybackActive: false }),
    )
    expect(buttonTagWithAriaLabel(html, 'Play')).toContain('disabled')
  })

  it('prev/next are disabled at the start/end of the real range', () => {
    const atStart = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2], selectedDay: 0 }))
    expect(buttonTagWithAriaLabel(atStart, 'Previous day')).toContain('disabled')
    const atEnd = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2], selectedDay: 2 }))
    expect(buttonTagWithAriaLabel(atEnd, 'Next day')).toContain('disabled')
  })

  it('GEO-PAGE1-FINAL: reaching the real final date shows the exact required "Forecast complete · [date]" wording, only at the end', () => {
    const middle = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2], selectedDay: 1 }))
    expect(middle).not.toContain('Forecast complete')

    const atEnd = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, t0: '2020-09-28', availableDays: [0, 1, 2], selectedDay: 2 }))
    expect(atEnd).toContain('Forecast complete · 30 Sep 2020')
  })
})

describe('GEO-REACH-GRADIENT-01: the real nominal-reach readout is read verbatim, never computed independently', () => {
  it('renders no readout at all when nominalReachKm is absent (the default) -- byte-identical to every pre-existing caller', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2, 3, 4, 5, 6, 7], selectedDay: 3 }),
    )
    expect(html).not.toContain('Model-projected reach')
  })

  it('renders no readout on day 0/observed, even if a stray non-positive value is passed -- never a fabricated "0.0 km"', () => {
    for (const value of [null, undefined, 0, -1]) {
      const html = renderToStaticMarkup(
        React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2], selectedDay: 0, nominalReachKm: value }),
      )
      expect(html).not.toContain('Model-projected reach')
    }
  })

  it('renders the EXACT real value passed, formatted to one decimal, never a rounded-off or hardcoded number', () => {
    // Real day-3 and day-5 values confirmed live against the running
    // backend (2026-09-01, origin ORIGIN:Sri Lanka:2020-09-07).
    const day3 = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2, 3], selectedDay: 3, nominalReachKm: 11.839264329464253 }),
    )
    expect(day3).toContain('Model-projected reach: 11.8 km')

    const day5 = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2, 3, 4, 5], selectedDay: 5, nominalReachKm: 19.732107215773755 }),
    )
    expect(day5).toContain('Model-projected reach: 19.7 km')
    // Different real days show different real numbers -- proves the
    // readout tracks the passed value rather than a fixed/hardcoded one.
    expect(day3).not.toContain('19.7 km')
    expect(day5).not.toContain('11.8 km')
  })

  it('the single-available-day snapshot bar also shows the readout when a real value is passed', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [1], selectedDay: 1, nominalReachKm: 3.946421443154751 }),
    )
    expect(html).toContain('Model-projected reach: 3.9 km')
  })
})

describe('GEO-PAGE1-FINAL Section 18/19: the timeline dock never silently disappears while a real focus is still loading', () => {
  it('isLoadingFocus=false (the default) with no real t0 yet still renders nothing -- byte-identical to the pre-existing crash-prevention behavior', () => {
    expect(renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, t0: undefined, availableDays: [0], selectedDay: 0 }))).toBe('')
    expect(
      renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, t0: undefined, availableDays: [0], selectedDay: 0, isLoadingFocus: false })),
    ).toBe('')
  })

  it('isLoadingFocus=true with no real t0 yet renders an honest, non-empty loading dock -- never null, never a fabricated date', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: undefined, availableDays: [0], selectedDay: 0, isLoadingFocus: true }),
    )
    expect(html).not.toBe('')
    expect(html).toContain('Preparing spatial timeline')
    // Never invents a calendar date it does not actually have yet.
    expect(html).not.toMatch(/\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}/)
  })

  it('the loading dock is never worded as "RECONNECTING" -- that word is reserved for the operational push-transport state elsewhere in this feature', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: undefined, availableDays: [0], selectedDay: 0, isLoadingFocus: true }),
    )
    expect(html.toUpperCase()).not.toContain('RECONNECTING')
  })

  it('isLoadingFocus is ignored the instant a real t0 arrives -- the real populated timeline renders normally, never the loading dock', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: '2020-09-28', availableDays: [0, 1, 2], selectedDay: 0, isLoadingFocus: true }),
    )
    expect(html).not.toContain('Preparing spatial timeline')
    expect(html).toContain('28 Sep 2020')
  })
})

describe('Page 1 fixed 01-14 Sep 2026 presentation timeline', () => {
  it('renders the three major labels, active exact date, speed controls and all 14 selectable nodes', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, {
        ...baseProps,
        presentationDates: PAGE1_FORECAST_DATES,
        activeIndex: 7,
        playbackSpeed: 1,
        onChangeSpeed: noop,
      }),
    )
    expect(html).toContain('08 SEP 2026')
    expect(html).toContain('01 SEP')
    expect(html).toContain('07 SEP')
    expect(html).toContain('14 SEP')
    expect(html.match(/aria-label="Select \d{2} SEP 2026"/g)).toHaveLength(14)
    expect(html).toContain('0.5×')
    expect(html).toContain('1×')
    expect(html).toContain('2×')
  })

  it('stays on the final date with Play and Next disabled', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, {
        ...baseProps,
        presentationDates: PAGE1_FORECAST_DATES,
        activeIndex: 13,
        playbackSpeed: 1,
        onChangeSpeed: noop,
      }),
    )
    expect(html).toContain('Forecast complete · 14 SEP 2026')
    expect(buttonTagWithAriaLabel(html, 'Play')).toContain('disabled')
    expect(buttonTagWithAriaLabel(html, 'Next day')).toContain('disabled')
  })
})
