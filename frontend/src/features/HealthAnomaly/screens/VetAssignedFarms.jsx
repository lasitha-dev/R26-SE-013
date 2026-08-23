import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function VetAssignedFarms() {
  const [farms, setFarms] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchFarms = async () => {
      try {
        const token = localStorage.getItem("token")
        const response = await fetch("http://127.0.0.1:8000/api/vet/my-farms", {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        })
        if (response.ok) {
          const data = await response.json()
          setFarms(Array.isArray(data) ? data : [])
        }
      } catch (err) {
        console.error("Error fetching assigned farms:", err)
      } finally {
        setLoading(false)
      }
    }
    fetchFarms()
  }, [])

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-outline-variant/10">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold uppercase tracking-wider">
              Assigned Herd Networks
            </span>
            <span className="text-slate-500">•</span>
            <span className="text-slate-400 text-xs font-mono">Veterinary Jurisdiction</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
            Assigned Farms &amp; Agricultural Estates
          </h1>
          <p className="text-slate-400 text-xs md:text-sm mt-1">
            Registered livestock farms linked to your veterinary license for diagnostic oversight and care protocols.
          </p>
        </div>

        <Link
          to="/vet/diagnostics"
          className="px-4 py-2.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-xs flex items-center gap-2 shadow-lg shadow-primary/20 hover:brightness-110 active:scale-95 transition-all uppercase tracking-wider"
        >
          <span className="material-symbols-outlined text-base">psychology</span>
          Diagnose Livestock
        </Link>
      </div>

      {/* Loading Skeleton */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-card rounded-xl p-6 border border-white/5 animate-pulse space-y-4">
              <div className="h-10 bg-white/5 rounded-lg w-1/3"></div>
              <div className="h-6 bg-white/5 rounded w-3/4"></div>
              <div className="h-4 bg-white/5 rounded w-1/2"></div>
              <div className="h-10 bg-white/5 rounded"></div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && farms.length === 0 && (
        <div className="glass-card rounded-2xl p-12 text-center border border-dashed border-white/10 max-w-2xl mx-auto space-y-4">
          <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto shadow-glow-sm">
            <span className="material-symbols-outlined text-3xl">agriculture</span>
          </div>
          <h3 className="text-lg font-bold text-white">No Agricultural Estates Assigned Yet</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
            When farm owners link your veterinary license to their estate in settings, their herds and health telemetries will automatically synchronize here.
          </p>
        </div>
      )}

      {/* Farms Grid */}
      {!loading && farms.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {farms.map((farm) => (
            <div
              key={farm.id}
              className="glass-card rounded-xl p-6 border border-white/5 hover:border-emerald-500/30 transition-all flex flex-col justify-between space-y-4 group"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                    <span className="material-symbols-outlined text-xl">agriculture</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {farm.registration_number}
                  </span>
                </div>

                <h3 className="text-base font-bold text-white group-hover:text-emerald-400 transition-colors">
                  {farm.owner_name}&apos;s Dairy Estate
                </h3>
                <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                  <span className="material-symbols-outlined text-xs">person</span>
                  Owner: <span className="text-slate-300 font-semibold">{farm.owner_name}</span>
                </p>
                <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                  <span className="material-symbols-outlined text-xs">location_on</span>
                  {farm.location_district || 'Sri Lanka'}
                </p>
                {farm.latitude && farm.longitude && (
                  <p className="text-[10px] font-mono text-slate-500 mt-1 flex items-center gap-1">
                    <span className="material-symbols-outlined text-[12px] text-emerald-400">pin_drop</span>
                    GPS: {farm.latitude.toFixed(4)}, {farm.longitude.toFixed(4)}
                  </p>
                )}
              </div>

              {/* Status and Cattle counts */}
              <div className="space-y-3 pt-3 border-t border-white/5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-1.5 text-slate-400">
                    <span className="material-symbols-outlined text-sm text-emerald-400">pets</span>
                    <span className="font-bold text-white">{farm.total_animals}</span> Animals
                  </div>
                  {farm.alert_count > 0 ? (
                    <span className="px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 text-[10px] font-bold flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span>
                      {farm.alert_count} Alerts
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold">
                      Herd Healthy
                    </span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-2">
                  <Link
                    to={`/vet/farm/${farm.id}`}
                    className="flex-1 py-2 px-3 rounded-lg bg-surface-container-highest hover:bg-surface-container-high border border-white/10 text-white text-xs font-bold text-center transition-all flex items-center justify-center gap-1"
                  >
                    <span>View Herd</span>
                    <span className="material-symbols-outlined text-xs">arrow_forward</span>
                  </Link>
                  <Link
                    to={`/vet/diagnostics?farm_id=${farm.id}`}
                    className="py-2 px-3 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 text-xs font-bold transition-all flex items-center gap-1"
                    title="Launch AI Diagnostics"
                  >
                    <span className="material-symbols-outlined text-xs">psychology</span>
                    <span>Diagnose</span>
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

