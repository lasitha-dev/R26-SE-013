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

function geospatialTabClassName({ isActive }) {
  return [
    'rounded-full border px-3 py-1 font-medium transition-colors',
    'focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400',
    isActive
      ? 'border-emerald-400/30 bg-emerald-400/15 text-emerald-300'
      : 'border-white/10 bg-slate-900/70 text-slate-300 hover:text-white',
  ].join(' ')
}

export default function GeospatialLayout() {
  return (
    <GeospatialProvider>
      <nav aria-label="Geospatial Intelligence sections" className="mb-3 flex flex-wrap gap-1.5 border-b border-white/10 pb-2 text-sm">
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
