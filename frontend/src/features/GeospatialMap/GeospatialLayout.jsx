import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'

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

export default function GeospatialLayout() {
  return (
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
      <Outlet />
    </GeospatialProvider>
  )
}
