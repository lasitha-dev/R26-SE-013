import React, { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import GeospatialRouteBoundary from './components/GeospatialRouteBoundary'
import { GeospatialProvider } from './context/GeospatialContext'

/**
 * GEO-OWNED-HOST-WRAPPER-16D: the ONE place all three Geospatial pages
 * (Outbreak Map / My Area / Analysis & Trends) share a single
 * `GeospatialProvider` instance, so selection/transport state survives
 * switching between them -- the provider wraps the local tab nav AND
 * `<Outlet/>` together, never re-mounted per tab.
 *
 * Deliberately router-agnostic about its own mount point: every
 * destination below is a RELATIVE route ('.', 'my-area', 'analysis'),
 * never a hardcoded '/vet/geospatial', so this file works unchanged
 * regardless of which host path segment an eventual owner-applied
 * `App.jsx` route nests it under.
 *
 * Renders no header/sidebar of its own -- the host's `VetLayout`
 * already supplies both; this component only ever occupies the content
 * area VetLayout hands to its routed children. No auth, no
 * localStorage, no data fetching, no MapLibre camera control -- those
 * all remain the pages' own responsibility.
 */
const GEOSPATIAL_TABS = [
  { to: '.', label: 'Outbreak Map', end: true },
  { to: 'my-area', label: 'My Area', end: false },
  { to: 'analysis', label: 'Analysis & Trends', end: false },
]

// GEO31A: restyled with the host dashboard's REAL design tokens
// (`tailwind.config.js`'s `primary`/`on-surface-variant`/
// `surface-container-high`, already used by `VetLayout.jsx`/Clinical
// Overview) instead of ad-hoc slate/emerald utility colors, and a
// tighter, less pill-like radius (`rounded-md`, not `rounded-full`) --
// matches the approved reference's "compact segmented tab control,
// dark neutral container, no huge pills" requirement. Purely visual:
// same 3 tabs, same relative routes, same active-state logic, so My
// Area/Analysis & Trends keep working identically -- only the chrome
// they already share looks more like the rest of this dashboard.
function geospatialTabClassName({ isActive }) {
  return [
    'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
    'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary',
    isActive ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:bg-surface-container-high/60 hover:text-on-surface',
  ].join(' ')
}

/** Bumps when the signed-in session changes in another tab (the `storage`
 * event never fires in the tab that made the change; same-tab sign-in goes
 * through the login route, which unmounts this layout anyway). Used as a
 * React key so every cached Geospatial query, selection and stream is
 * dropped and rebuilt for the new identity -- the token itself is never
 * stored or displayed. */
function useSessionGeneration() {
  const [generation, setGeneration] = useState(0)
  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const onStorage = (event) => {
      if (event.key === null || event.key === 'token' || event.key === 'role') setGeneration((g) => g + 1)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])
  return generation
}

export default function GeospatialLayout() {
  const sessionGeneration = useSessionGeneration()
  const { pathname } = useLocation()
  return (
    <React.Fragment key={sessionGeneration}>
    <GeospatialProvider>
      <nav
        aria-label="Geospatial Intelligence sections"
        className="mb-2 ml-auto flex w-fit flex-wrap gap-1 rounded-lg border border-outline-variant/30 bg-surface-container-high/40 p-1"
      >
        {GEOSPATIAL_TABS.map((tab) => (
          <NavLink key={tab.label} to={tab.to} end={tab.end} className={geospatialTabClassName}>
            {tab.label}
          </NavLink>
        ))}
      </nav>
      {/* A page render error stays inside this area: the host shell and the
          tabs above remain usable (see GeospatialRouteBoundary). */}
      <GeospatialRouteBoundary resetKey={pathname}>
        <Outlet />
      </GeospatialRouteBoundary>
    </GeospatialProvider>
    </React.Fragment>
  )
}
