import React, { useRef } from 'react'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { act, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MIN_HEIGHT_PX, useAvailableMapHeight } from '../context/useAvailableMapHeight'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

let observers = []
class FakeResizeObserver {
  constructor(callback) { this.callback = callback; this.targets = []; this.disconnected = false; observers.push(this) }
  observe(target) { this.targets.push(target) }
  disconnect() { this.disconnected = true }
}

let wrapperTop = 273
function Probe() {
  const ref = useRef(null)
  const height = useAvailableMapHeight(ref)
  return <div ref={ref} data-testid="wrapper" data-height={height} />
}

beforeEach(() => {
  observers = []
  wrapperTop = 273
  vi.stubGlobal('ResizeObserver', FakeResizeObserver)
  vi.stubGlobal('requestAnimationFrame', (cb) => { cb(); return 1 })
  vi.stubGlobal('cancelAnimationFrame', () => {})
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({ top: wrapperTop }))
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 900 })
})
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('National Map viewport fit', () => {
  it('re-measures when a row renders above the map after mount (measured 1440x900: 273 -> 303 px)', () => {
    const { getByTestId, unmount } = render(<Probe />)
    expect(getByTestId('wrapper').dataset.height).toBe(String(900 - 273 - 16))

    wrapperTop = 303
    act(() => observers[0].callback([]))
    expect(getByTestId('wrapper').dataset.height).toBe(String(900 - 303 - 16))
    expect(observers[0].targets).toContain(document.body)

    unmount()
    expect(observers[0].disconnected).toBe(true)
  })

  it('never goes below the minimum height', () => {
    wrapperTop = 800
    const { getByTestId } = render(<Probe />)
    expect(getByTestId('wrapper').dataset.height).toBe(String(MIN_HEIGHT_PX))
  })

  it('the measured height is not overridden by a larger fixed floor or a zero flex-basis', () => {
    const canvas = readFileSync(join(ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf8')
    const page = readFileSync(join(ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf8')
    expect(canvas).toContain(`min-h-[${MIN_HEIGHT_PX}px]`)
    expect(canvas).not.toMatch(/min-h-\[(?!480px)\d+px\]/)
    expect(page).toMatch(/className="relative min-h-\[480px\] shrink-0[^"]*"\s*\n\s*style=\{\{ height: availableMapHeight \}\}/)
  })
})
