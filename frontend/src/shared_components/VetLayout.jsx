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

  const [notifications, setNotifications] = useState([])
  const [isNotifOpen, setIsNotifOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  const token = localStorage.getItem("token")

  const fetchNotifications = async () => {
    if (!token || vetInfo.role !== 'vet') return
    try {
      const res = await fetch('http://127.0.0.1:8000/api/vet/notifications', {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const notifData = await res.json()
        setNotifications(notifData || [])
        setUnreadCount((notifData || []).filter(n => !n.read).length)
      }
    } catch (err) {
      // ignore
    }
  }

  // Check alert status across herds and fetch notifications
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
    fetchNotifications()
    const interval = setInterval(fetchNotifications, 20000)
    return () => clearInterval(interval)
  }, [token])

  const handleMarkAsRead = async (notifId) => {
    try {
      await fetch(`http://127.0.0.1:8000/api/vet/notifications/${notifId}/read`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` }
      })
      setNotifications(prev => prev.map(n => n.id === notifId ? { ...n, read: true } : n))
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (err) {
      // ignore
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await fetch(`http://127.0.0.1:8000/api/vet/notifications/read-all`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      })
      setNotifications(prev => prev.map(n => ({ ...n, read: true })))
      setUnreadCount(0)
    } catch (err) {
      // ignore
    }
  }

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
                {vetInfo.role === 'daph' ? 'DAPH Forecasting Portal' : 'Vet Clinical Portal'}
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
            {vetInfo.role === 'daph' ? 'National Disease Oversight' : 'Veterinary Authority'}
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
                placeholder={vetInfo.role === 'daph' ? 'Search national forecasts, advisories, or disease trends...' : 'Search case records, assigned herds, or pathology reports...'}
                type="text"
              />
            </div>
          </div>

          {/* Right Header Badges & Actions */}
          <div className="flex items-center gap-4">
            {/* Live Clinical Node Indicator */}
            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>{vetInfo.role === 'daph' ? 'DAPH NATIONAL SCOPE' : 'VET NODE LIVE'}</span>
            </div>

            {/* Notification Bell with Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setIsNotifOpen(!isNotifOpen)}
                className="w-10 h-10 flex items-center justify-center text-slate-400 hover:text-emerald-300 transition-colors relative rounded-lg hover:bg-white/5"
                title="Clinical Notifications & Disease Reports"
              >
                <span className="material-symbols-outlined">notifications</span>
                {unreadCount > 0 ? (
                  <>
                    <span className="absolute top-1.5 right-1.5 w-4 h-4 bg-red-500 rounded-full text-[9px] font-bold text-white flex items-center justify-center border-2 border-[#0b1326] animate-pulse font-mono">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  </>
                ) : hasAlerts ? (
                  <span className="absolute top-2 right-2 w-2 h-2 bg-amber-400 rounded-full border-2 border-[#0b1326]"></span>
                ) : null}
              </button>

              {/* Notification Dropdown Panel */}
              {isNotifOpen && (
                <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-[#0f172a] border border-emerald-500/20 rounded-2xl shadow-2xl z-50 overflow-hidden animate-fadeIn">
                  <div className="px-4 py-3 bg-surface-container border-b border-white/5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-emerald-400 text-lg">medical_services</span>
                      <span className="text-xs font-bold text-white uppercase tracking-wider font-mono">Clinical Alerts</span>
                      {unreadCount > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 text-[10px] font-bold">
                          {unreadCount} New
                        </span>
                      )}
                    </div>
                    {unreadCount > 0 && (
                      <button
                        onClick={handleMarkAllRead}
                        className="text-[10px] text-emerald-400 hover:underline font-mono font-bold"
                      >
                        Mark all read
                      </button>
                    )}
                  </div>

                  <div className="max-h-80 overflow-y-auto divide-y divide-white/5 no-scrollbar">
                    {notifications.length === 0 ? (
                      <div className="p-6 text-center text-slate-400 space-y-1">
                        <span className="material-symbols-outlined text-2xl text-slate-600">notifications_off</span>
                        <p className="text-xs font-semibold">No pending disease notifications</p>
                      </div>
                    ) : (
                      notifications.map((notif) => (
                        <div
                          key={notif.id}
                          onClick={() => {
                            handleMarkAsRead(notif.id)
                            setIsNotifOpen(false)
                            navigate('/vet/clinical-records')
                          }}
                          className={`p-3.5 hover:bg-surface-container/60 cursor-pointer transition-colors space-y-1 ${
                            !notif.read ? 'bg-amber-500/5' : ''
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold font-mono text-amber-400 uppercase flex items-center gap-1">
                              {!notif.read && <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>}
                              {notif.type || 'FARMER_DISEASE_REPORT'}
                            </span>
                            <span className="text-[9px] text-slate-500 font-mono">{notif.created_at?.split(' ')[0] || 'Today'}</span>
                          </div>
                          <p className="text-xs font-bold text-white">{notif.disease_name} • {notif.farm_name || 'Assigned Farm'}</p>
                          <p className="text-[11px] text-slate-300 leading-snug">{notif.message}</p>
                          <div className="pt-1 flex items-center justify-between text-[10px]">
                            <span className="font-mono text-slate-400">Tag: {notif.animal_identifier || 'COW-TAG'}</span>
                            <span className="text-emerald-400 font-bold flex items-center gap-0.5">
                              Review Case <span className="material-symbols-outlined text-xs">arrow_forward</span>
                            </span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="p-2.5 bg-surface-container/80 border-t border-white/5 text-center">
                    <Link
                      to="/vet/clinical-records"
                      onClick={() => setIsNotifOpen(false)}
                      className="text-xs text-emerald-400 font-bold uppercase tracking-wider hover:underline inline-flex items-center gap-1"
                    >
                      <span>Open Clinical Records</span>
                      <span className="material-symbols-outlined text-sm">launch</span>
                    </Link>
                  </div>
                </div>
              )}
            </div>

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
                <p className="text-xs font-bold text-on-surface">
                  {vetInfo.role === 'daph' ? 'DAPH Official' : vetInfo.fullName}
                </p>
                <p className="text-[10px] text-emerald-400/80 font-mono">
                  {vetInfo.role === 'daph' ? 'National Scope' : (vetInfo.licenseNumber || 'Verified Practitioner')}
                </p>
              </div>
              <div className="w-8 h-8 rounded-full bg-surface-container-highest overflow-hidden border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-glow-sm">
                <span className="material-symbols-outlined text-lg">
                  {vetInfo.role === 'daph' ? 'public' : 'stethoscope'}
                </span>
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
