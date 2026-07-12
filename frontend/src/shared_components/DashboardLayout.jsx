import React, { useState, useContext } from 'react'
import { NavLink, Outlet, Navigate, useNavigate } from 'react-router-dom'
import { ProfileContext } from '../context/ProfileContext.jsx'

export default function DashboardLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const { profilePhoto, farmerName } = useContext(ProfileContext)
  const navigate = useNavigate()


  const token = localStorage.getItem("token")

  if (!token) {
    return <Navigate to="/health/login" replace />
  }

  const ownerDisplayName = farmerName || localStorage.getItem("owner_name") || "Julian Vane"
  const vetName = localStorage.getItem("veterinarian_name") || "Clinical Lead"

  const navLinks = [
    { to: '/health/dashboard', label: 'Wellness & BCS', icon: 'health_and_safety' },
    { to: '/health/herd-registry', label: 'Herd Registry', icon: 'pets' },
    { to: '/health/ai-wellness-report', label: 'AI Smart Diagnosis', icon: 'memory' },
    { to: '/health/geospatial', label: 'Geospatial Intelligence', icon: 'map' },
    { to: '/health/forecasting', label: 'Seasonal Forecasting', icon: 'partly_cloudy_day' },
  ]

  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
      isActive
        ? 'text-emerald-400 font-bold border-r-2 border-emerald-500 bg-emerald-500/5'
        : 'text-slate-400 hover:text-emerald-200 hover:bg-emerald-500/10'
    }`

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
        <div className="px-6 mb-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-500 rounded flex items-center justify-center">
              <span
                className="material-symbols-outlined text-white text-xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                shield
              </span>
            </div>
            <div>
              <h1 className="text-white font-bold tracking-tight leading-none text-base uppercase">
                ADRS CORE
              </h1>
              <p className="text-[10px] uppercase tracking-widest text-emerald-500/60 mt-0.5">
                Clinical Precision
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

        {/* Navigation Items */}
        <nav className="flex-grow px-3 space-y-1 overflow-y-auto no-scrollbar">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={linkClass}
              onClick={() => setIsSidebarOpen(false)}
            >
              <span className="material-symbols-outlined text-[20px]">{link.icon}</span>
              <span className="text-sm">{link.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Sidebar Footer */}
        <div className="px-4 pb-6 mt-auto border-t border-white/5 pt-4 space-y-1">
          <NavLink
            to="/health/settings"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2 rounded-lg transition-colors text-sm ${
                isActive ? 'text-emerald-400 font-bold bg-emerald-500/5' : 'text-slate-400 hover:text-emerald-200'
              }`
            }
            onClick={() => setIsSidebarOpen(false)}
          >
            <span className="material-symbols-outlined text-[20px]">settings</span>
            <span>Settings</span>
          </NavLink>
          <button
            onClick={() => {
              localStorage.clear()
              navigate('/health/login')
            }}
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
                placeholder="Search livestock ID or wellness reports..."
                type="text"
              />
            </div>
          </div>

          {/* Right Header Badges & Actions */}
          <div className="flex items-center gap-4">
            <NavLink
              to="/health/notifications"
              className="w-10 h-10 flex items-center justify-center text-slate-400 hover:text-emerald-300 transition-colors relative"
            >
              <span className="material-symbols-outlined">notifications</span>
              <span className="absolute top-2 right-2 w-2 h-2 bg-emerald-500 rounded-full border-2 border-[#0b1326]"></span>
            </NavLink>
            <NavLink
              to="/health/settings"
              className="w-10 h-10 flex items-center justify-center text-slate-400 hover:text-emerald-300 transition-colors"
            >
              <span className="material-symbols-outlined">settings</span>
            </NavLink>
            <div className="h-6 w-px bg-white/10 mx-1"></div>
            <div className="flex items-center gap-3 pl-2 border-l border-white/10">
              <div className="text-right hidden md:block">
                <p className="text-xs font-bold text-on-surface">{ownerDisplayName}</p>
                <p className="text-[10px] text-slate-500">{vetName}</p>
              </div>
              <div className="w-8 h-8 rounded-full bg-surface-container-highest overflow-hidden border border-emerald-500/20">
                {profilePhoto ? (
                  <img
                    alt="User profile"
                    className="w-full h-full object-cover"
                    src={profilePhoto}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-emerald-500/10 text-emerald-400">
                    <span className="material-symbols-outlined text-lg">person</span>
                  </div>
                )}
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
