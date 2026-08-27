import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function NotificationsCenter() {
  const navigate = useNavigate()
  const [cattleList, setCattleList] = useState([])
  const [forecastNotifications, setForecastNotifications] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchCattle = async () => {
      try {
        const token = localStorage.getItem('token')
        const response = await fetch('http://127.0.0.1:8000/api/cattle', {
          headers: {
            Authorization: token ? `Bearer ${token}` : ''
          }
        })
        if (response.ok) {
          const data = await response.json()
          setCattleList(data || [])
        }
        
        // Fetch Forecasting Notifications
        const forecastRes = await fetch('/api/v1/risk-forecasting/notifications', {
          headers: {
            Authorization: token ? `Bearer ${token}` : ''
          }
        })
        if (forecastRes.ok) {
          const forecastData = await forecastRes.json()
          setForecastNotifications(forecastData || [])
        }
      } catch (err) {
        console.error('Error loading notifications:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchCattle()
  }, [])

  const alerts = cattleList.filter(c => c.health_status === 'Alert' || c.status === 'Alert')

  return (
    <div className="space-y-8">
      {/* Back Button & Title Area */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link
              to="/health/dashboard"
              className="flex items-center gap-1 text-primary-fixed uppercase text-[10px] font-black tracking-[0.3em] hover:underline"
            >
              <span className="material-symbols-outlined text-xs">arrow_back</span>
              Back to Dashboard
            </Link>
            <div className="h-px w-12 bg-outline-variant/30"></div>
          </div>
          <h2 className="text-xs font-bold text-primary tracking-[0.2em] uppercase mt-2 mb-1">
            Diagnostic Interface
          </h2>
          <h1 className="text-4xl font-black text-on-surface tracking-tighter uppercase">
            System Notifications &amp; AI Alerts
          </h1>
        </div>
      </div>

      {/* Notifications List */}
      <div className="space-y-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center p-12 bg-surface-container-low rounded-xl border border-white/5">
            <span className="material-symbols-outlined text-4xl text-primary animate-spin">progress_activity</span>
            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mt-3">Loading active alerts...</p>
          </div>
        ) : (
          <>
            {/* Render Dynamic AI Health Alerts */}
            {alerts.map((c) => (
              <div key={c.id} className="group relative overflow-hidden bg-surface-container-low rounded-xl transition-all hover:bg-surface-container-high border border-white/5">
                <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-error"></div>
                <div className="p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
                  <div className="w-14 h-14 rounded-lg bg-error-container/20 flex items-center justify-center flex-shrink-0 animate-pulse">
                    <span className="material-symbols-outlined text-3xl text-error">warning</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="px-2 py-0.5 text-[10px] font-black bg-error/10 text-error rounded tracking-tighter uppercase animate-bounce">
                        AI Critical Alert
                      </span>
                      <span className="text-[10px] text-slate-500 font-medium">RECENT DETECTION</span>
                    </div>
                    <h3 className="text-xl font-bold text-on-surface tracking-tight mb-2">
                      Action Required: Health Anomaly Flagged
                    </h3>
                    <p className="text-slate-400 text-sm leading-relaxed max-w-2xl">
                      🚨 Health Alert: Cattle <span className="text-on-surface font-mono font-bold">{c.identifier}</span> ({c.breed}) has a potential health anomaly. Please check the profile and initiate triage.
                    </p>
                  </div>
                  <div className="flex-shrink-0 pt-4 md:pt-0">
                    <button
                      onClick={() => navigate(`/health/animal-profile/${c.id}`)}
                      className="bg-error text-on-error px-6 py-3 rounded-lg font-bold text-sm flex items-center gap-2 hover:bg-error/90 active:scale-95 transition-all shadow-lg shadow-error/10"
                    >
                      View Profile & Triage
                      <span className="material-symbols-outlined text-sm">arrow_forward</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {/* Render Risk Forecasting Notifications */}
            {forecastNotifications.map((n) => (
              <div key={n._id} className="group relative overflow-hidden bg-surface-container-low rounded-xl transition-all hover:bg-surface-container-high border border-white/5">
                <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-warning"></div>
                <div className="p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
                  <div className="w-14 h-14 rounded-lg bg-warning-container/20 flex items-center justify-center flex-shrink-0 animate-pulse">
                    <span className="material-symbols-outlined text-3xl text-warning">campaign</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="px-2 py-0.5 text-[10px] font-black bg-warning/10 text-warning rounded tracking-tighter uppercase animate-bounce">
                        Disease Advisory
                      </span>
                      <span className="text-[10px] text-slate-500 font-medium">{new Date(n.created_at).toLocaleDateString()}</span>
                    </div>
                    <h3 className="text-xl font-bold text-on-surface tracking-tight mb-2">
                      {n.title}
                    </h3>
                    <p className="text-slate-400 text-sm leading-relaxed max-w-2xl">
                      {n.message}
                    </p>
                  </div>
                  </div>
                </div>
              </div>
            ))}

            {/* Environmental Warning */}
            <div className="group relative overflow-hidden bg-surface-container-low rounded-xl transition-all hover:bg-surface-container-high border border-white/5">
              <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-secondary-container"></div>
              <div className="p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
                <div className="w-14 h-14 rounded-lg bg-secondary-container/10 flex items-center justify-center flex-shrink-0">
                  <span className="material-symbols-outlined text-3xl text-secondary">device_thermostat</span>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="px-2 py-0.5 text-[10px] font-black bg-secondary-container/20 text-secondary rounded tracking-tighter uppercase">
                      Environmental Warning
                    </span>
                    <span className="text-[10px] text-slate-500 font-medium">2 HOURS AGO</span>
                  </div>
                  <h3 className="text-xl font-bold text-on-surface tracking-tight mb-2">
                    Environmental Stress Alert
                  </h3>
                  <p className="text-slate-400 text-sm leading-relaxed max-w-2xl">
                    Geospatial sensors indicate THI (Temperature Humidity Index) has reached{' '}
                    <span className="text-secondary font-bold">79</span> (Critical limit: 78). High probability of
                    decreased rumination and metabolic heat accumulation. Heat stress protocols recommended for
                    Sector B.
                  </p>
                </div>
                <div className="flex-shrink-0 pt-4 md:pt-0">
                  <button
                    onClick={() => navigate('/health/geospatial')}
                    className="bg-surface-container-highest text-secondary border border-secondary/30 px-6 py-3 rounded-lg font-bold text-sm flex items-center gap-2 hover:bg-secondary/10 active:scale-95 transition-all"
                  >
                    View Heatmap
                    <span className="material-symbols-outlined text-sm">map</span>
                  </button>
                </div>
              </div>
            </div>

            {/* System Info */}
            <div className="group relative overflow-hidden bg-surface-container-low rounded-xl transition-all hover:bg-surface-container-high border border-white/5">
              <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-primary-container"></div>
              <div className="p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
                <div className="w-14 h-14 rounded-lg bg-primary-container/10 flex items-center justify-center flex-shrink-0">
                  <span className="material-symbols-outlined text-3xl text-primary">check_circle</span>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="px-2 py-0.5 text-[10px] font-black bg-primary-container/20 text-primary rounded tracking-tighter uppercase">
                      System Info
                    </span>
                    <span className="text-[10px] text-slate-500 font-medium">06:00 AM TODAY</span>
                  </div>
                  <h3 className="text-xl font-bold text-on-surface tracking-tight mb-2">System Sync Complete</h3>
                  <p className="text-slate-400 text-sm leading-relaxed max-w-2xl">
                    Daily physiological logs, genomic markers, and herd registry data successfully encrypted and backed
                    up to <span className="text-primary">Sentinel Cloud Architecture</span>. Integrity check: 100%
                    verified. Next scheduled sync: 24h.
                  </p>
                </div>
                <div className="flex-shrink-0 pt-4 md:pt-0">
                  <span className="text-xs text-slate-500 uppercase tracking-widest font-bold pl-4">Verified</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Stats Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 bg-surface-container-low rounded-xl border border-outline-variant/10">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-primary">analytics</span>
            <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500">Alert Efficiency</h4>
          </div>
          <p className="text-2xl font-bold text-on-surface">98.4%</p>
          <p className="text-xs text-slate-500 mt-1">Accuracy in predictive triage this month</p>
        </div>
        <div className="p-6 bg-surface-container-low rounded-xl border border-outline-variant/10">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-secondary">update</span>
            <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500">
              Avg. Response Time
            </h4>
          </div>
          <p className="text-2xl font-bold text-on-surface">12m 40s</p>
          <p className="text-xs text-slate-500 mt-1">From detection to clinical intervention</p>
        </div>
        <div className="p-6 bg-surface-container-low rounded-xl border border-outline-variant/10">
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined text-error">monitoring</span>
            <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500">Active Monitoring</h4>
          </div>
          <p className="text-2xl font-bold text-on-surface">{cattleList.length}</p>
          <p className="text-xs text-slate-500 mt-1">Active livestock units under real-time AI scan</p>
        </div>
      </div>
    </div>
  )
}
