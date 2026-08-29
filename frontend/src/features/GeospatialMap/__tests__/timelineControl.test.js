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
  it('renders nothing before an outbreak is selected (only D0 available -- collapsed)', () => {
    const html = renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [0], selectedDay: 0 }))
    expect(html).toBe('')
  })

  it('renders nothing when availableDays is empty/undefined', () => {
    expect(renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: [], selectedDay: 0 }))).toBe('')
    expect(renderToStaticMarkup(React.createElement(TimelineControl, { ...baseProps, availableDays: undefined, selectedDay: 0 }))).toBe('')
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
    expect(html).toContain('28 Sep 2020') // D0
    expect(html).toContain('30 Sep 2020') // D+2, month has not rolled over here
  })

  it('correctly rolls over a month boundary in the rendered dates', () => {
    const html = renderToStaticMarkup(
      React.createElement(TimelineControl, { ...baseProps, t0: '2020-09-28', availableDays: [0, 1, 2, 3, 4], selectedDay: 0 }),
    )
    expect(html).toContain('2 Oct 2020') // D+4 rolls into October
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
