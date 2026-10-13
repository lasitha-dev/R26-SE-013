import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import ObservedTimelineControl from '../components/ObservedTimelineControl'

const noop = () => {}
const baseProps = {
  isPlaybackActive: false,
  onSelectDate: noop,
  onPlay: noop,
  onPause: noop,
  onPrev: noop,
  onNext: noop,
  windowLabel: 'Last 30 days',
  emptyStateText: 'No verified LSD cases in My District · Matara',
  reduceMotion: false,
}

function buttonTagWithAriaLabel(html, label) {
  const re = new RegExp(`<button[^>]*aria-label="${label}"[^>]*>`)
  const match = html.match(re)
  return match ? match[0] : null
}

// A `disabled:opacity-40` Tailwind class always contains the literal
// substring "disabled" -- a plain `.toContain('disabled')` check would
// false-positive on that class name alone. Check for the real HTML
// attribute instead.
function isActuallyDisabled(buttonTag) {
  return /\sdisabled(=|>|\s)/.test(buttonTag)
}

describe('GEO31A/GEO33A Section 5/13/14/15: ObservedTimelineControl always renders in Cases mode', () => {
  it('zero real observed dates: still renders (never null), shows the honest empty-state text, Play disabled', () => {
    const html = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...baseProps, dates: [], selectedDateKey: null }))
    expect(html).not.toBe('')
    expect(html).toContain('Observed')
    expect(html).toContain('Last 30 days')
    expect(html).toContain('No verified LSD cases in My District · Matara')
    expect(isActuallyDisabled(buttonTagWithAriaLabel(html, 'Play'))).toBe(true)
  })

  it('never fabricates a date tick when there are zero real dates', () => {
    const html = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...baseProps, dates: [], selectedDateKey: null }))
    expect(html).not.toMatch(/aria-current/)
  })

  it('real observed dates: renders one pill per real date, at latest by default (last date active)', () => {
    const dates = ['2026-08-24', '2026-08-29', '2026-08-30']
    const html = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...baseProps, dates, selectedDateKey: null }))
    expect(html).toContain('24 Aug 2026')
    expect(html).toContain('29 Aug 2026')
    expect(html).toContain('30 Aug 2026')
    expect(isActuallyDisabled(buttonTagWithAriaLabel(html, 'Play'))).toBe(false)
  })

  it('a single real observed date still disables Play (nothing to advance to)', () => {
    const html = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...baseProps, dates: ['2026-08-30'], selectedDateKey: null }))
    expect(isActuallyDisabled(buttonTagWithAriaLabel(html, 'Play'))).toBe(true)
  })

  it('prev is disabled at the earliest real date, next is disabled at latest (default)', () => {
    const dates = ['2026-08-24', '2026-08-29', '2026-08-30']
    const atStart = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...baseProps, dates, selectedDateKey: dates[0] }))
    expect(isActuallyDisabled(buttonTagWithAriaLabel(atStart, 'Previous observed date'))).toBe(true)
    const atLatest = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...baseProps, dates, selectedDateKey: null }))
    expect(isActuallyDisabled(buttonTagWithAriaLabel(atLatest, 'Next observed date'))).toBe(true)
  })
})
