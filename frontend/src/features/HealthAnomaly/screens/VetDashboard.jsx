import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function VetDashboard() {
  const navigate = useNavigate()
  const [farmsList, setFarmsList] = useState([])
  const [cattleList, setCattleList] = useState([])
  const [loading, setLoading] = useState(true)
  const [vetName, setVetName] = useState(
    localStorage.getItem("full_name") || localStorage.getItem("owner_name") || "Clinical Veterinarian"
  )
  const [licenseNumber, setLicenseNumber] = useState(
    localStorage.getItem("license_number") || "VET-AUTH-2026"
  )

  useEffect(() => {
    const fetchDashboardData = async () => {
      const token = localStorage.getItem("token")
      try {
        const farmsResp = await fetch("http://127.0.0.1:8000/api/vet/my-farms", {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        })

        if (farmsResp.ok) {
          const farms = await farmsResp.json()
          setFarmsList(Array.isArray(farms) ? farms : [])

          // Aggregate cattle across all assigned farms
          const allCattle = []
          for (const farm of farms) {
            try {
              const cattleResp = await fetch(`http://127.0.0.1:8000/api/vet/farms/${farm.id}/cattle`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {}
              })
              if (cattleResp.ok) {
                const cattleData = await cattleResp.json()
                if (cattleData.cattle && Array.isArray(cattleData.cattle)) {
                  allCattle.push(...cattleData.cattle)
                }
              }
            } catch (err) {
              // continue
            }
          }
          setCattleList(allCattle)
        }
      } catch (err) {
        console.error("Error fetching vet dashboard data:", err)
      } finally {
        setLoading(false)
      }
    }
    fetchDashboardData()
  }, [])

  const alertsCount = cattleList.filter(
    (c) => c.health_status === 'Alert' || c.status === 'Alert'
  ).length

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-surface-container-high via-surface-container to-surface-container-low border border-primary/20 p-6 md:p-8 shadow-2xl">
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-[radial-gradient(ellipse_at_top_right,rgba(78,222,163,0.15),transparent_70%)] pointer-events-none" />
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-mono font-bold uppercase tracking-wider">
                Authorized Clinical Practitioner
              </span>
              <span className="text-slate-500">•</span>
              <span className="text-slate-400 text-xs font-mono">{licenseNumber}</span>
            </div>
            <h1 className="text-2xl md:text-3xl lg:text-4xl font-extrabold text-white tracking-tight">
              Welcome back, {vetName}
            </h1>
            <p className="text-slate-400 text-sm mt-1.5 max-w-2xl leading-relaxed">
              Real-time multi-herd clinical telemetry, automated pathology triage, and AI computer vision diagnostics.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <button
              onClick={() => navigate('/vet/diagnostics')}
              className="px-5 py-3 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-sm flex items-center gap-2 shadow-lg shadow-primary/20 hover:brightness-110 active:scale-95 transition-all uppercase tracking-wider"
            >
              <span className="material-symbols-outlined text-lg">psychology</span>
              Launch AI Diagnostics
            </button>
            <Link
              to="/vet/assigned-farms"
              className="px-4 py-3 rounded-xl bg-surface-container-highest/60 border border-white/10 text-on-surface hover:bg-surface-container-highest font-semibold text-sm flex items-center gap-2 transition-all"
            >
              <span className="material-symbols-outlined text-lg text-emerald-400">agriculture</span>
              Assigned Farms
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        <div className="glass-card rounded-xl p-5 border border-white/5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Livestock Monitored</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
              <span className="material-symbols-outlined text-lg">pets</span>
            </div>
          </div>
          <p className="text-3xl font-extrabold text-white">{cattleList.length}</p>
          <p className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
            <span className="material-symbols-outlined text-xs">check_circle</span>
            Active Telemetry Feeds
          </p>
        </div>

        <div className="glass-card rounded-xl p-5 border border-white/5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Health Anomalies</span>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${alertsCount > 0 ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
              <span className="material-symbols-outlined text-lg">{alertsCount > 0 ? 'warning' : 'verified'}</span>
            </div>
          </div>
          <p className="text-3xl font-extrabold text-white">{alertsCount}</p>
          <p className={`text-[11px] mt-1 flex items-center gap-1 ${alertsCount > 0 ? 'text-red-400' : 'text-slate-400'}`}>
            <span className="material-symbols-outlined text-xs">{alertsCount > 0 ? 'error' : 'shield'}</span>
            {alertsCount > 0 ? 'Requires Clinical Review' : 'All Herds Stable'}
          </p>
        </div>

        <div className="glass-card rounded-xl p-5 border border-white/5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Linked Agro Herds</span>
            <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
              <span className="material-symbols-outlined text-lg">agriculture</span>
            </div>
          </div>
          <p className="text-3xl font-extrabold text-white">{farmsList.length}</p>
          <p className="text-[11px] text-primary mt-1 flex items-center gap-1 font-mono">
            <span className="material-symbols-outlined text-xs">corporate_fare</span>
            Assigned Agricultural Estates
          </p>
        </div>

        <div className="glass-card rounded-xl p-5 border border-white/5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">License Status</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
              <span className="material-symbols-outlined text-lg">verified_user</span>
            </div>
          </div>
          <p className="text-2xl font-extrabold text-emerald-400">Verified</p>
          <p className="text-[11px] text-slate-400 mt-1 font-mono">
            Council Validated
          </p>
        </div>
      </div>

      {/* Main Two-Column Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Health Anomaly Watchlist */}
        <div className="lg:col-span-2 glass-card rounded-xl p-6 border border-white/5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-white/5">
            <div className="flex items-center gap-2.5">
              <span className="material-symbols-outlined text-primary text-xl">medical_information</span>
              <h2 className="text-lg font-bold text-white">Active Livestock Clinical Watchlist</h2>
            </div>
            <span className="text-xs text-slate-400 font-mono">{cattleList.length} recorded</span>
          </div>

          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-3">
              <span className="material-symbols-outlined text-3xl animate-spin text-primary">progress_activity</span>
              <p className="text-xs">Synchronizing herd health data...</p>
            </div>
          ) : cattleList.length === 0 ? (
            <div className="py-12 text-center text-slate-400 space-y-2">
              <span className="material-symbols-outlined text-4xl text-slate-600">inventory_2</span>
              <p className="text-sm font-semibold text-slate-300">No livestock records assigned yet.</p>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Livestock records registered by assigned farm owners will populate here for clinical telemetry and diagnostics.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto no-scrollbar">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-400 uppercase tracking-wider border-b border-white/5 font-mono">
                    <th className="py-3 px-3 font-semibold">Animal ID</th>
                    <th className="py-3 px-3 font-semibold">Estate / Location</th>
                    <th className="py-3 px-3 font-semibold">Breed</th>
                    <th className="py-3 px-3 font-semibold">Health Status</th>
                    <th className="py-3 px-3 font-semibold text-right">Clinical Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {cattleList.slice(0, 8).map((c) => {
                    const isAlert = c.health_status === 'Alert' || c.status === 'Alert'
                    return (
                      <tr key={c.id || c.identifier} className="hover:bg-surface-container-high/40 transition-colors">
                        <td className="py-3 px-3 font-bold text-white font-mono flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${isAlert ? 'bg-red-400 animate-pulse' : 'bg-emerald-400'}`} />
                          {c.identifier}
                        </td>
                        <td className="py-3 px-3 text-slate-300 text-[11px]">
                          <span className="font-semibold text-white">{c.farm_name || 'Assigned Farm'}</span>
                          {c.farm_location && <span className="text-slate-500 block text-[10px] truncate max-w-[140px]">{c.farm_location}</span>}
                        </td>
                        <td className="py-3 px-3 text-slate-300">{c.breed || 'Jersey'}</td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                              isAlert
                                ? 'bg-red-500/15 text-red-400 border border-red-500/30'
                                : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            }`}
                          >
                            {isAlert ? 'Alert' : 'Healthy'}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={() => navigate(`/vet/diagnostics?cattle_id=${c.id}&farm_id=${c.farm_id || ''}`)}
                            className="text-primary hover:text-primary-fixed font-bold inline-flex items-center gap-1 hover:underline"
                          >
                            <span>Diagnose</span>
                            <span className="material-symbols-outlined text-xs">arrow_forward</span>
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: Quick Action & Model Reasoning Hub */}
        <div className="space-y-6">
          {/* AI Diagnostics Feature Card */}
          <div className="glass-card rounded-xl p-6 border border-primary/20 bg-gradient-to-b from-surface-container to-surface-container-lowest space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/20 text-primary flex items-center justify-center shadow-glow-sm">
                <span className="material-symbols-outlined text-2xl">psychology</span>
              </div>
              <div>
                <h3 className="font-bold text-white text-base">Smart Diagnostics</h3>
                <p className="text-[11px] text-slate-400">Multi-stage computer vision triage</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Upload clinical animal imagery to perform automated YOLOv8 cattle detection, ViT disease classification, and Mask R-CNN lesion segmentation.
            </p>

            <button
              onClick={() => navigate('/vet/diagnostics')}
              className="w-full py-3 bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-xs rounded-lg uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-primary/15 hover:brightness-110 transition-all"
            >
              <span className="material-symbols-outlined text-base">upload_file</span>
              Open Diagnostics Workbench
            </button>
          </div>

          {/* Clinical Protocols Summary */}
          <div className="glass-card rounded-xl p-6 border border-white/5 space-y-3">
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-400 text-base">policy</span>
              Veterinary Protocol Compliance
            </h3>
            <div className="space-y-2 text-xs text-slate-400">
              <div className="flex items-center justify-between p-2 rounded-lg bg-surface-container-lowest border border-white/5">
                <span>Council Telemetry Sync</span>
                <span className="text-emerald-400 font-mono font-bold">Enabled</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-surface-container-lowest border border-white/5">
                <span>BCS Vision Calibration</span>
                <span className="text-emerald-400 font-mono font-bold">Calibrated</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-surface-container-lowest border border-white/5">
                <span>Diagnostic Token Expiry</span>
                <span className="text-slate-300 font-mono">24 Hours</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
