import React, { useState, useEffect } from 'react'
import { NavLink, Outlet, Navigate, useNavigate, useLocation } from 'react-router-dom'

export default function VetLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [vetInfo, setVetInfo] = useState({
    fullName: localStorage.getItem("full_name") || localStorage.getItem("owner_name") || "Dr. Clinical Vet",
    email: localStorage.getItem("email") || "",
    licenseNumber: localStorage.getItem("license_number") || "VET-AUTH-2026",
    role: localStorage.getItem("role")
  })
  const [hasAlerts, setHasAlerts] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const token = localStorage.getItem("token")

  // Check alert status across herds
  useEffect(() => {
    const fetchVetData = async () => {
      if (!token) return
      try {
        const response = await fetch('http://127.0.0.1:8000/api/cattle', {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        if (response.ok) {
          const data = await response.json()
          const alertExists = Array.isArray(data) && data.some(c => c.health_status === 'Alert' || c.status === 'Alert')
          setHasAlerts(alertExists)
        }
      } catch (err) {
        // Silently catch in dev
      }
    }
    fetchVetData()
  }, [token])

  if (!token || (vetInfo.role !== 'vet' && vetInfo.role !== 'daph')) {
    return <Navigate to="/vet/login" replace />
  }

  const allNavLinks = [
    { to: '/vet/dashboard', label: 'Clinical Overview', icon: 'health_and_safety', allowedRoles: ['vet'] },
    { to: '/vet/assigned-farms', label: 'Smart Diagnostics', icon: 'psychology', matchPrefixes: ['/vet/assigned-farms', '/vet/farm', '/vet/diagnostics'], allowedRoles: ['vet'] },
    { to: '/vet/geospatial', label: 'Geospatial Intelligence', icon: 'travel_explore', allowedRoles: ['vet'] },
    { to: '/vet/forecasting', label: 'Seasonal Forecasting', icon: 'partly_cloudy_day', allowedRoles: ['vet', 'daph'] },
  ]

  const vetNavLinks = allNavLinks.filter(link => link.allowedRoles.includes(vetInfo.role))

  const handleSignOut = () => {
    localStorage.clear()
    navigate('/vet/login')
  }

  return (
    <div className="min-h-screen bg-background text-on-surface antialiased selection:bg-primary/30">
      {/* Mobile Sidebar Backdrop / Overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden transition-opacity duration-300"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed left-0 top-0 h-screen w-64 bg-[#131b2e] border-r border-emerald-500/10 flex flex-col py-6 tracking-tight z-50 transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Logo and Brand */}
        <div className="px-6 mb-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-emerald-500 rounded-lg flex items-center justify-center shadow-glow-sm">
              <span
                className="material-symbols-outlined text-white text-xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                medical_services
              </span>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="text-white font-bold tracking-tight leading-none text-base uppercase">
                  ADRS CORE
                </h1>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              </div>
              <p className="text-[10px] uppercase tracking-widest text-emerald-400/80 mt-1 font-mono font-semibold">
                Vet Clinical Portal
              </p>
            </div>
          </div>

          {/* Mobile Close Button */}
          <button
            className="lg:hidden text-slate-400 hover:text-emerald-300 transition-colors p-1"
            onClick={() => setIsSidebarOpen(false)}
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        {/* Section Badge */}
        <div className="px-6 mb-3">
          <span className="text-[10px] uppercase font-bold tracking-widest text-slate-500 font-mono">
            Veterinary Authority
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="flex-grow px-3 space-y-1 overflow-y-auto no-scrollbar">
          {vetNavLinks.map((link) => {
            const isActive = link.matchPrefixes
              ? link.matchPrefixes.some(prefix => pathname === prefix || pathname.startsWith(prefix + '/') || pathname.startsWith(prefix + '?'))
              : (pathname === link.to || (link.to !== '/vet/dashboard' && pathname.startsWith(link.to)))
            const cls = `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
              isActive
                ? 'text-emerald-400 font-bold border-r-2 border-emerald-500 bg-emerald-500/10 shadow-glow-sm'
                : 'text-slate-400 hover:text-emerald-200 hover:bg-emerald-500/5'
            }`
            return (
              <NavLink
                key={link.to}
                to={link.to}
                className={cls}
                onClick={() => setIsSidebarOpen(false)}
              >
                <span className="material-symbols-outlined text-[20px]">{link.icon}</span>
                <span className="text-sm">{link.label}</span>
              </NavLink>
            )
          })}
        </nav>

        {/* Sidebar Footer */}
        <div className="px-4 pb-6 mt-auto border-t border-white/5 pt-4 space-y-1">
          {vetInfo.role === 'vet' && (
            <NavLink
              to="/vet/settings"
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2 rounded-lg transition-colors text-sm ${
                  isActive ? 'text-emerald-400 font-bold bg-emerald-500/5' : 'text-slate-400 hover:text-emerald-200'
                }`
              }
              onClick={() => setIsSidebarOpen(false)}
            >
              <span className="material-symbols-outlined text-[20px]">badge</span>
              <span>License &amp; Profile</span>
            </NavLink>
          )}
          <button
            onClick={handleSignOut}
            className="w-full flex items-center gap-3 px-4 py-2 text-slate-400 hover:text-red-400 transition-colors text-sm text-left"
            type="button"
          >
            <span className="material-symbols-outlined text-[20px] text-red-400/80">logout</span>
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="lg:pl-64 min-h-screen flex flex-col">
        {/* Sticky Header */}
        <header className="sticky top-0 z-30 bg-[#0b1326]/80 backdrop-blur-xl border-b border-white/5 flex justify-between items-center h-16 px-4 md:px-8 font-medium text-sm">
          <div className="flex items-center gap-4 flex-1">
            {/* Hamburger Toggle for Mobile */}
            <button
              className="lg:hidden text-slate-400 hover:text-emerald-300 transition-colors p-1"
              onClick={() => setIsSidebarOpen(true)}
              aria-label="Open sidebar"
            >
              <span className="material-symbols-outlined text-2xl">menu</span>
            </button>

            {/* Search Input */}
            <div className="relative w-full max-w-md group hidden sm:block">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg group-focus-within:text-emerald-500 transition-colors">
                search
              </span>
              <input
                className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all placeholder:text-slate-500"
                placeholder="Search case records, assigned herds, or pathology reports..."
                type="text"
              />
            </div>
          </div>

          {/* Right Header Badges & Actions */}
          <div className="flex items-center gap-4">
            {/* Live Clinical Node Indicator */}
            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>VET NODE LIVE</span>
            </div>

            <NavLink
              to="/vet/dashboard"
              className="w-10 h-10 flex items-center justify-center text-slate-400 hover:text-emerald-300 transition-colors relative"
              title="Notifications"
            >
              <span className="material-symbols-outlined">notifications</span>
              {hasAlerts ? (
                <>
                  <span className="absolute top-2 right-2 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-[#0b1326] animate-ping"></span>
                  <span className="absolute top-2 right-2 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-[#0b1326]"></span>
                </>
              ) : (
                <span className="absolute top-2 right-2 w-2 h-2 bg-emerald-500 rounded-full border-2 border-[#0b1326]"></span>
              )}
            </NavLink>

            {vetInfo.role === 'vet' && (
              <NavLink
                to="/vet/settings"
                className="w-10 h-10 flex items-center justify-center text-slate-400 hover:text-emerald-300 transition-colors"
                title="Vet Credentials"
              >
                <span className="material-symbols-outlined">badge</span>
              </NavLink>
            )}

            <div className="h-6 w-px bg-white/10 mx-1"></div>

            {/* Practitioner Profile Badge */}
            <div className="flex items-center gap-3 pl-2 border-l border-white/10">
              <div className="text-right hidden md:block">
                <p className="text-xs font-bold text-on-surface">{vetInfo.fullName}</p>
                <p className="text-[10px] text-emerald-400/80 font-mono">
                  {vetInfo.licenseNumber || 'Verified Practitioner'}
                </p>
              </div>
              <div className="w-8 h-8 rounded-full bg-surface-container-highest overflow-hidden border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-glow-sm">
                <span className="material-symbols-outlined text-lg">stethoscope</span>
              </div>
            </div>
          </div>
        </header>

        {/* Content Outlet with Responsive Padding */}
        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-7xl mx-auto w-full">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
