import React, { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export default function VetFarmCattleView() {
  const { farmId } = useParams()
  const navigate = useNavigate()

  const [farm, setFarm] = useState(null)
  const [cattleList, setCattleList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL') // 'ALL', 'ALERT', 'HEALTHY'
  const [successBanner, setSuccessBanner] = useState('')

  // Mortality modal states
  const [showMortalityModal, setShowMortalityModal] = useState(false)
  const [selectedCattleForMortality, setSelectedCattleForMortality] = useState(null)
  const [deathCause, setDeathCause] = useState('FMD')
  const [deathDate, setDeathDate] = useState(new Date().toISOString().split('T')[0])
  const [deathNotes, setDeathNotes] = useState('')
  const [submittingDeath, setSubmittingDeath] = useState(false)
  const [deathError, setDeathError] = useState('')

  const handleMortalityClick = (cattle) => {
    setSelectedCattleForMortality(cattle)
    setDeathCause('FMD')
    setDeathDate(new Date().toISOString().split('T')[0])
    setDeathNotes('')
    setDeathError('')
    setShowMortalityModal(true)
  }

  const handleDeclareDeceasedSubmit = async (e) => {
    e.preventDefault()
    if (!selectedCattleForMortality) return
    setSubmittingDeath(true)
    setDeathError('')
    
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`${API_BASE}/api/vet/cattle/${selectedCattleForMortality.id}/declare-deceased`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          cause: deathCause,
          date_of_death: deathDate,
          notes: deathNotes
        })
      })
      
      if (response.ok) {
        const updated = await response.json()
        setCattleList(prev => prev.map(c => c.id === updated.id ? { ...c, ...updated } : c))
        setShowMortalityModal(false)
        setSuccessBanner(`Successfully reported mortality for cattle ${selectedCattleForMortality.identifier}.`)
        setTimeout(() => setSuccessBanner(''), 5000)
      } else {
        const data = await response.json()
        setDeathError(data.detail || 'Failed to update cattle status as deceased.')
      }
    } catch (err) {
      setDeathError('Network error. Unable to declare cattle deceased.')
    } finally {
      setSubmittingDeath(false)
    }
  }

  useEffect(() => {
    const fetchFarmCattle = async () => {
      setLoading(true)
      setError('')
      try {
        const token = localStorage.getItem('token')
        const response = await fetch(`${API_BASE}/api/vet/farms/${farmId}/cattle`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        })

        if (response.ok) {
          const data = await response.json()
          setFarm(data.farm || null)
          setCattleList(Array.isArray(data.cattle) ? data.cattle : [])
        } else {
          const errData = await response.json()
          setError(errData.detail || 'Unable to retrieve cattle records for this farm.')
        }
      } catch (err) {
        setError('Cannot connect to server. Ensure backend is running.')
      } finally {
        setLoading(false)
      }
    }

    if (farmId) {
      fetchFarmCattle()
    }
  }, [farmId])

  const filteredCattle = cattleList.filter((cattle) => {
    const matchesSearch =
      cattle.identifier?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      cattle.breed?.toLowerCase().includes(searchQuery.toLowerCase())

    const isDeceased = cattle.status === 'Deceased' || cattle.health_status === 'Deceased'
    const isAlert = !isDeceased && (cattle.health_status === 'Alert' || cattle.status === 'Alert')
    const matchesStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'ALERT' && isAlert) ||
      (statusFilter === 'HEALTHY' && !isAlert && !isDeceased)

    return matchesSearch && matchesStatus
  })

  const alertCount = cattleList.filter(
    (c) => c.status !== 'Deceased' && c.health_status !== 'Deceased' && (c.health_status === 'Alert' || c.status === 'Alert')
  ).length

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center gap-3">
        <Link
          to="/vet/assigned-farms"
          className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 text-xs font-mono font-bold uppercase tracking-wider transition-colors"
        >
          <span className="material-symbols-outlined text-sm">arrow_back</span>
          Back to Assigned Farms
        </Link>
        <span className="text-slate-600">•</span>
        <span className="text-slate-400 text-xs font-mono">Herd Intake &amp; Telemetry</span>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-6 bg-error/15 border border-error/30 rounded-2xl text-error space-y-2">
          <div className="flex items-center gap-2 font-bold text-sm">
            <span className="material-symbols-outlined">gpp_maybe</span>
            <span>Authorization / Network Notice</span>
          </div>
          <p className="text-xs">{error}</p>
          <button
            onClick={() => navigate('/vet/assigned-farms')}
            className="mt-3 px-4 py-2 bg-error/20 hover:bg-error/30 text-white rounded-lg text-xs font-bold uppercase tracking-wider transition-all"
          >
            Return to Farms List
          </button>
        </div>
      )}

      {successBanner && (
        <div className="p-4 bg-emerald-500/15 border border-emerald-500/30 rounded-xl text-emerald-400 font-semibold text-xs flex items-center gap-2">
          <span className="material-symbols-outlined">check_circle</span>
          <span>{successBanner}</span>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && !error && (
        <div className="space-y-6 animate-pulse">
          <div className="h-36 bg-white/5 rounded-2xl"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-56 bg-white/5 rounded-xl"></div>
            ))}
          </div>
        </div>
      )}

      {/* Farm Overview Header Card */}
      {!loading && !error && farm && (
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#131b2e] via-[#0f172a] to-[#0b1326] border border-emerald-500/20 p-6 md:p-8 shadow-2xl">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold uppercase">
                  {farm.registration_number || 'REG-AGRO-LK'}
                </span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-400 text-xs font-mono">
                  {farm.location_district || 'Regional Agricultural Node'}
                </span>
                {farm.latitude && farm.longitude && (
                  <span className="px-2 py-0.5 rounded bg-white/5 text-slate-400 text-[10px] font-mono border border-white/10 flex items-center gap-1">
                    <span className="material-symbols-outlined text-[12px] text-emerald-400">pin_drop</span>
                    {farm.latitude.toFixed(4)}, {farm.longitude.toFixed(4)}
                  </span>
                )}
              </div>

              <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                {farm.owner_name}&apos;s Herd Registry
              </h1>
              <p className="text-xs md:text-sm text-slate-400 flex items-center gap-4">
                <span>Principal: <strong className="text-slate-200">{farm.owner_name}</strong></span>
                <span>Contact: <strong className="text-slate-200">{farm.email}</strong></span>
              </p>
            </div>

            {/* Quick Metrics & Actions */}
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-3 bg-surface-container-lowest/60 border border-white/10 rounded-xl px-4 py-3">
                <div className="text-right">
                  <p className="text-[10px] uppercase font-mono text-slate-400">Active Herd</p>
                  <p className="text-xl font-bold text-white font-mono">{cattleList.length}</p>
                </div>
                <div className="h-8 w-px bg-white/10"></div>
                <div className="text-right">
                  <p className="text-[10px] uppercase font-mono text-slate-400">Health Alerts</p>
                  <p className={`text-xl font-bold font-mono ${alertCount > 0 ? 'text-red-400 animate-pulse' : 'text-emerald-400'}`}>
                    {alertCount}
                  </p>
                </div>
              </div>

              <Link
                to={`/vet/diagnostics?farm_id=${farm.id}`}
                className="px-5 py-3 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-xs flex items-center gap-2 shadow-lg shadow-primary/20 hover:brightness-110 active:scale-95 transition-all uppercase tracking-wider"
              >
                <span className="material-symbols-outlined text-base">psychology</span>
                Smart Diagnostics
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Search & Filter Toolbar */}
      {!loading && !error && (
        <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4 bg-surface-container-low p-4 rounded-xl border border-white/5">
          {/* Search bar */}
          <div className="relative flex-1 max-w-md">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-base">
              search
            </span>
            <input
              type="text"
              placeholder="Search ear tag ID or breed..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-2 pl-9 pr-3 text-xs text-white placeholder-slate-500 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 transition-all"
            />
          </div>

          {/* Status Filters */}
          <div className="flex items-center gap-2">
            {[
              { id: 'ALL', label: 'All Animals' },
              { id: 'ALERT', label: `Alerts (${alertCount})` },
              { id: 'HEALTHY', label: 'Healthy' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold uppercase tracking-wider transition-all border ${
                  statusFilter === tab.id
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : 'bg-surface-container-lowest text-slate-400 border-white/5 hover:text-white'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Cattle Grid */}
      {!loading && !error && (
        <>
          {filteredCattle.length === 0 ? (
            <div className="glass-card rounded-2xl p-12 text-center border border-dashed border-white/10 max-w-xl mx-auto space-y-3">
              <span className="material-symbols-outlined text-slate-500 text-4xl">pets</span>
              <p className="text-sm font-bold text-white">No Cattle Records Found</p>
              <p className="text-xs text-slate-400">
                {searchQuery || statusFilter !== 'ALL'
                  ? 'No cattle match the active search and filter criteria.'
                  : 'The farm owner has not registered any cattle under this agricultural estate yet.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredCattle.map((cattle) => {
                const isDeceased = cattle.status === 'Deceased' || cattle.health_status === 'Deceased'
                const isAlert = !isDeceased && (cattle.health_status === 'Alert' || cattle.status === 'Alert')
                return (
                  <div
                    key={cattle.id}
                    className={`glass-card rounded-xl p-5 border transition-all flex flex-col justify-between space-y-4 group ${
                      isDeceased
                        ? 'border-slate-800 bg-slate-900/40 opacity-75'
                        : isAlert
                        ? 'border-red-500/30 bg-red-500/5 hover:border-red-500/60'
                        : 'border-white/5 hover:border-emerald-500/30'
                    }`}
                  >
                    <div>
                      {/* Top Header */}
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 rounded-xl bg-surface-container-highest overflow-hidden border border-white/10 flex items-center justify-center flex-shrink-0">
                            {cattle.profile_photo ? (
                              <img
                                src={cattle.profile_photo}
                                alt={cattle.identifier}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <span className="material-symbols-outlined text-2xl text-emerald-400">
                                pets
                              </span>
                            )}
                          </div>
                          <div>
                            <h3 className="text-base font-extrabold text-white font-mono group-hover:text-emerald-400 transition-colors">
                              {cattle.identifier}
                            </h3>
                            <p className="text-xs text-slate-400">{cattle.breed}</p>
                          </div>
                        </div>

                        {/* Status Badge */}
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider flex items-center gap-1 border ${
                            isDeceased
                              ? 'bg-slate-500/20 text-slate-400 border-slate-500/45'
                              : isAlert
                              ? 'bg-red-500/20 text-red-300 border-red-500/40'
                              : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          }`}
                        >
                          {isAlert && <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span>}
                          {isDeceased ? 'Deceased' : isAlert ? 'Alert' : 'Healthy'}
                        </span>
                      </div>

                      {/* Specs Matrix */}
                      <div className="grid grid-cols-3 gap-2 py-3 border-y border-white/5 text-center font-mono">
                        <div className="bg-surface-container-lowest/50 p-2 rounded-lg">
                          <p className="text-[10px] text-slate-500 uppercase">Weight</p>
                          <p className="text-xs font-bold text-slate-200 mt-0.5">{cattle.weight || '--'} kg</p>
                        </div>
                        <div className="bg-surface-container-lowest/50 p-2 rounded-lg">
                          <p className="text-[10px] text-slate-500 uppercase">BCS Score</p>
                          <p className="text-xs font-bold text-emerald-400 mt-0.5">
                            {cattle.bcs_score !== null && cattle.bcs_score !== undefined
                              ? Number(cattle.bcs_score).toFixed(1)
                              : '--'}
                          </p>
                        </div>
                        <div className="bg-surface-container-lowest/50 p-2 rounded-lg">
                          <p className="text-[10px] text-slate-500 uppercase">Gender</p>
                          <p className="text-xs font-bold text-slate-200 mt-0.5">{cattle.gender || 'Female'}</p>
                        </div>
                      </div>

                      {isDeceased && cattle.death_cause && (
                        <div className="mt-2 px-2.5 py-1 bg-red-950/20 border border-red-500/10 rounded-lg text-[10px] text-red-400 font-mono flex items-center gap-1.5">
                          <span className="material-symbols-outlined text-xs">info</span>
                          <span>Cause: {cattle.death_cause} {cattle.death_date ? `(${cattle.death_date})` : ''}</span>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="pt-2 flex flex-col gap-2 w-full">
                      {isDeceased ? (
                        <div className="flex flex-col gap-1 w-full">
                          <button
                            disabled
                            className="w-full py-2 px-3 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-500 font-bold text-xs uppercase tracking-wider text-center flex items-center justify-center gap-1.5 cursor-not-allowed"
                            title="Diagnostics locked for deceased cattle"
                          >
                            <span className="material-symbols-outlined text-sm">lock</span>
                            Run AI Diagnostic
                          </button>
                          <span className="text-[9px] text-center text-slate-500 font-mono">
                            Diagnostics locked for deceased cattle
                          </span>
                        </div>
                      ) : (
                        <div className="flex gap-2 w-full">
                          <Link
                            to={`/vet/diagnostics?cattle_id=${cattle.id}&farm_id=${farm.id}`}
                            className="flex-1 py-2 px-3 rounded-lg bg-gradient-to-r from-emerald-500/20 to-primary-container/20 hover:from-emerald-500/30 hover:to-primary-container/30 border border-emerald-500/30 text-emerald-300 font-bold text-xs uppercase tracking-wider text-center flex items-center justify-center gap-1.5 transition-all shadow-glow-sm"
                          >
                            <span className="material-symbols-outlined text-sm">psychology</span>
                            Diagnose
                          </Link>
                          <button
                            onClick={() => handleMortalityClick(cattle)}
                            className="py-2 px-3 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-300 font-bold text-xs uppercase tracking-wider text-center flex items-center justify-center gap-1 transition-all shrink-0"
                          >
                            <span className="material-symbols-outlined text-sm">skull</span>
                            Mortality
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
      {/* Mortality Modal */}
      {showMortalityModal && selectedCattleForMortality && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f172a] border border-red-500/20 max-w-md w-full rounded-2xl p-6 shadow-2xl space-y-4 animate-scaleUp text-white">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-red-400">skull</span>
                <span>Report Cattle Mortality</span>
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Tag ID: <strong className="text-slate-200">{selectedCattleForMortality.identifier}</strong> ({selectedCattleForMortality.breed})
              </p>
            </div>
            
            <form onSubmit={handleDeclareDeceasedSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-mono font-bold uppercase text-slate-400">Date of Death</label>
                <input
                  type="date"
                  required
                  value={deathDate}
                  onChange={(e) => setDeathDate(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-red-500"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-mono font-bold uppercase text-slate-400">Cause of Death</label>
                <select
                  value={deathCause}
                  onChange={(e) => setDeathCause(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-red-500"
                >
                  <option value="FMD">Foot-and-Mouth Disease (FMD)</option>
                  <option value="LSD">Lumpy Skin Disease (LSD)</option>
                  <option value="Other">Other / General Mortality</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-mono font-bold uppercase text-slate-400">Notes / Remarks</label>
                <textarea
                  value={deathNotes}
                  onChange={(e) => setDeathNotes(e.target.value)}
                  placeholder="Provide clinical context, symptoms, or autopsy findings..."
                  rows="3"
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-red-500 placeholder-slate-600"
                />
              </div>

              {deathError && (
                <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">error</span>
                  <span>{deathError}</span>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowMortalityModal(false)}
                  disabled={submittingDeath}
                  className="flex-1 py-2 px-4 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white text-xs font-bold font-mono transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingDeath}
                  className="flex-1 py-2 px-4 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-bold font-mono transition-all flex items-center justify-center gap-1"
                >
                  {submittingDeath ? (
                    <>
                      <span className="material-symbols-outlined text-xs animate-spin">progress_activity</span>
                      <span>Reporting...</span>
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined text-xs">check</span>
                      <span>Declare Deceased</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
