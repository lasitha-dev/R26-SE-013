import { useEffect, useState } from 'react'

// GEO26B Section 5: a small breathing-room margin below the map card --
// a Geospatial-owned DESIGN choice (matches this page's own `gap-2`
// rhythm), not a guess about the host sidebar/header's pixel height.
const BOTTOM_MARGIN_PX = 16
const MIN_HEIGHT_PX = 480

/**
 * GEO26B Section 5: replaces the previous `height: calc(100vh - 220px)`
 * guess. `VetLayout.jsx` (read-only, another member's file) gives its
 * `<main>` no fixed/bounded height -- it's `min-h-screen` with ordinary
 * document flow, not an app-shell with a known chrome height -- so a
 * pure-CSS flex/`h-full` chain has nothing bounded to inherit from here.
 * Instead of guessing a constant for "sidebar + header + padding", this
 * MEASURES the wrapper's real distance from the current viewport bottom
 * at runtime and uses that -- correct regardless of header height,
 * sidebar state, page zoom, or window size, and re-measured on resize
 * and orientation change. `MapLibreCanvas.jsx`'s own `ResizeObserver`
 * (Section 1 of the audit) then handles the actual internal map canvas
 * resize once this height changes.
 */
export function useAvailableMapHeight(wrapperRef) {
  const [height, setHeight] = useState(MIN_HEIGHT_PX)

  useEffect(() => {
    function measure() {
      const el = wrapperRef.current
      if (!el || typeof window === 'undefined') return
      const top = el.getBoundingClientRect().top
      const available = window.innerHeight - top - BOTTOM_MARGIN_PX
      setHeight(Math.max(MIN_HEIGHT_PX, Math.floor(available)))
    }

    measure()
    window.addEventListener('resize', measure)
    window.addEventListener('orientationchange', measure)
    return () => {
      window.removeEventListener('resize', measure)
      window.removeEventListener('orientationchange', measure)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return height
}

export { MIN_HEIGHT_PX }
