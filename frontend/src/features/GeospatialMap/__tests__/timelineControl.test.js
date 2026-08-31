import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import TimelineControl from '../components/TimelineControl'

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
    expect(html).toContain('D0')
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

  it('GEO-UI-TIMELINE-01 Part 3B: the real calendar date is the PRIMARY label -- it appears before the D0/D+N horizon index in document order, both in the single-frame snapshot and in the multi-day pill row', () => {
    const single = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [0], selectedDay: 0 }))
    expect(single.indexOf('28 Sep 2020')).toBeLessThan(single.indexOf('D0'))

    const multi = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2], selectedDay: 1 }),
    )
    // The always-visible header states the real selected date before its
    // own D+N index...
    expect(multi.indexOf('29 Sep 2020')).toBeLessThan(multi.indexOf('D+1'))
    // ...and each individual pill also shows its own real date ahead of
    // its own D-index, not the reverse.
    const firstPillDate = multi.indexOf('28 Sep')
    const firstPillDIndex = multi.indexOf('D0')
    expect(firstPillDate).toBeGreaterThan(0)
    expect(firstPillDate).toBeLessThan(firstPillDIndex)
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

  it('expands once the real multi-day horizon is available, showing D0 through the REAL last day only (D+7, never D+14)', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, availableDays: [0, 1, 2, 3, 4, 5, 6, 7], selectedDay: 0 }),
    )
    expect(html).toContain('D0')
    expect(html).toContain('D+7')
    expect(html).not.toContain('D+8')
    expect(html).not.toContain('D+14')
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
    expect(html).toContain('28 Sep 2020') // header, D0 (selected)
    expect(html).toContain('28 Sep') // pill, D0
    expect(html).toContain('29 Sep') // pill, D+1
    expect(html).toContain('30 Sep') // pill, D+2 -- month has not rolled over here
  })

  it('correctly rolls over a month boundary in the rendered dates', () => {
    // Select D+4 itself so the always-visible header (which states the
    // full year-bearing date of the SELECTED day) is the one exercising
    // the rollover -- the per-pill trimmed label is checked separately.
    const selected = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: '2020-09-28', availableDays: [0, 1, 2, 3, 4], selectedDay: 4 }),
    )
    expect(selected).toContain('2 Oct 2020') // D+4 rolls into October, header (selected)

    const unselected = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: '2020-09-28', availableDays: [0, 1, 2, 3, 4], selectedDay: 0 }),
    )
    expect(unselected).toContain('2 Oct') // D+4 pill, real date still rolls over even when not selected
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
