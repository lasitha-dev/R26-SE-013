import { useEffect, useState } from 'react'

/** `prefers-reduced-motion: reduce` (plan Section 28). Read once via
 * `matchMedia` and kept in sync if the user changes it mid-session --
 * consumers use this to skip camera-fit animation, the reach-ring
 * grow/shrink tween, and the selected-marker pulse, while keeping every
 * piece of information identical either way. */
export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (event) => setReduced(event.matches)
    query.addEventListener('change', handler)
    return () => query.removeEventListener('change', handler)
  }, [])

  return reduced
}
