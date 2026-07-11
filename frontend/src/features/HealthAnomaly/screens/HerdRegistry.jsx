import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { calculateAge } from './AddNewAnimal.jsx'

export default function HerdRegistry() {
  const [cattleList, setCattleList] = useState([])
  const [loading, setLoading] = useState(true)

  const statusStyles = {
    Healthy: {
      pill: 'bg-primary/10 text-primary',
      dot: 'bg-primary',
    },
    'At Risk': {
      pill: 'bg-error/10 text-error',
      dot: 'bg-error',
    },
  }

  useEffect(() => {
    const fetchCattle = async () => {
      try {
        const token = localStorage.getItem('token')
        const response = await fetch('http://127.0.0.1:8000/api/cattle', {
          headers: {
            Authorization: token ? `Bearer ${token}` : '',
          },
        })
        if (response.ok) {
          const data = await response.json()
          setCattleList(data || [])
        }
      } catch (err) {
        console.error('Error fetching cattle list:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchCattle()
  }, [])

  // ─── Dynamic Top Statistics ────────────────────────────────────────────────
  const totalLivestock = cattleList.length
  const healthyCount = cattleList.filter((c) => c.status === 'Healthy').length
  const pendingAlertsCount = cattleList.filter((c) => c.status !== 'Healthy').length

  const bioSecurityScore =
    totalLivestock > 0 ? Math.round((healthyCount / totalLivestock) * 100) : 100

  // ─── Dynamic Breed Composition ─────────────────────────────────────────────
  const getBreedPercentage = (breedName) => {
    const count = cattleList.filter(
      (c) => c.breed && c.breed.toLowerCase() === breedName.toLowerCase()
    ).length
    return totalLivestock > 0 ? Math.round((count / totalLivestock) * 100) : 0
  }

  // Map API cattle array to table rows
  const displayRows = cattleList.map((c) => ({
    id: c.identifier,
    dot: c.status === 'Healthy' ? 'bg-primary' : 'bg-error',
    gender: c.gender,
    dob: `${c.dob} (${calculateAge(c.dob)})`,
    breed: c.breed,
    status: {
      label: c.status,
      color: c.status === 'Healthy' ? 'Healthy' : 'At Risk',
      pulse: c.status !== 'Healthy',
    },
    profile_photo: c.profile_photo,
  }))

  return (
    <div className="space-y-8">
      {/* Title Bar with Add Button */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-black tracking-tight text-white uppercase">HERD REGISTRY</h2>
          <div className="flex items-center gap-4 text-slate-400 text-xs tracking-widest uppercase font-medium">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-primary rounded-full"></span>{' '}
              {totalLivestock} Total Livestock
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full"></span>{' '}
              {bioSecurityScore}% Bio-Security Score
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-error rounded-full"></span>{' '}
              {pendingAlertsCount} Pending Alerts
            </span>
          </div>
        </div>
        <Link
          to="/health/add-new-animal"
          className="self-start sm:self-auto px-6 py-3 bg-primary-container text-on-primary-container font-bold rounded-lg flex items-center gap-2 hover:opacity-90 transition-all active:scale-[0.98]"
        >
          <span className="material-symbols-outlined">add</span>
          Add New Animal
        </Link>
      </div>

      {/* Population & Breed Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8 bg-surface-container-low rounded-xl p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
            <span className="material-symbols-outlined text-[120px] text-primary">analytics</span>
          </div>
          <div className="relative z-10">
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-6">Population Health Trends</h3>
            <div className="flex items-end gap-2 h-32 px-2">
              {[60, 75, 55, 90, 85, 95].map((h, idx) => (
                <div
                  key={idx}
                  className="w-full bg-primary/20 rounded-t hover:bg-primary/40 transition-all"
                  style={{ height: `${h}%` }}
                ></div>
              ))}
              <div className="w-full bg-primary rounded-t hover:bg-primary/80 transition-all relative" style={{ height: '80%' }}>
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-surface text-primary text-[10px] font-bold px-2 py-1 rounded border border-primary/20 whitespace-nowrap">
                  OPT-MAX
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 bg-surface-container-low rounded-xl p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Breed Composition</h3>
            <p className="text-xs text-slate-500">Distribution analysis across primary herds</p>
          </div>
          <div className="space-y-3 mt-4">
            {[
              { name: 'Friesian', color: 'bg-primary', textCls: 'text-primary' },
              { name: 'Jersey', color: 'bg-secondary', textCls: 'text-secondary' },
              { name: 'Sahiwal', color: 'bg-tertiary', textCls: 'text-tertiary' },
              { name: 'Local', color: 'bg-primary-container', textCls: 'text-primary-container' },
            ].map((b) => {
              const pct = getBreedPercentage(b.name)
              return (
                <div key={b.name} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-300">{b.name}</span>
                    <span className={`text-xs font-bold ${b.textCls}`}>{pct}%</span>
                  </div>
                  <div className="w-full h-1 bg-surface rounded-full overflow-hidden">
                    <div
                      className={`h-full ${b.color} transition-all duration-500`}
                      style={{ width: `${pct}%` }}
                    ></div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Active Registry Table */}
      <div className="bg-surface-container-low rounded-xl overflow-hidden">
        <div className="px-8 py-6 flex items-center justify-between border-b border-surface/50">
          <h3 className="text-lg font-bold text-white tracking-tight">Active Animal Registry</h3>
          <div className="flex items-center gap-2">
            <button
              className="p-2 hover:bg-surface-container-high rounded transition-colors text-slate-400"
              type="button"
            >
              <span className="material-symbols-outlined">filter_list</span>
            </button>
            <button
              className="p-2 hover:bg-surface-container-high rounded transition-colors text-slate-400"
              type="button"
            >
              <span className="material-symbols-outlined">download</span>
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-lowest/50 text-slate-400 text-[10px] uppercase tracking-[0.2em] font-bold">
                <th className="px-8 py-4">Identifier (Tag / Name)</th>
                <th className="px-6 py-4">Gender</th>
                <th className="px-6 py-4">DOB &amp; Age</th>
                <th className="px-6 py-4">Breed</th>
                <th className="px-6 py-4">Current Health Status</th>
                <th className="px-8 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface/30">
              {loading ? (
                <tr>
                  <td colSpan="6" className="px-8 py-12 text-center">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <span className="material-symbols-outlined text-4xl text-primary animate-spin">
                        progress_activity
                      </span>
                      <p className="font-bold tracking-wider uppercase text-[10px] text-slate-400">
                        Loading Cattle Records...
                      </p>
                    </div>
                  </td>
                </tr>
              ) : displayRows.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-8 py-16 text-center">
                    <div className="flex flex-col items-center justify-center gap-2 text-slate-450">
                      <span className="material-symbols-outlined text-5xl text-slate-500 mb-2">
                        database_off
                      </span>
                      <p className="font-black tracking-wider uppercase text-xs text-slate-400">
                        No animals found in registry
                      </p>
                      <p className="text-xs text-slate-500 max-w-xs mx-auto">
                        Add a new animal record to start monitoring bio-security and physical parameters.
                      </p>
                      <Link
                        to="/health/add-new-animal"
                        className="inline-flex items-center gap-1.5 px-4 py-2 mt-4 bg-primary/10 border border-primary/20 text-primary text-xs font-bold rounded-lg hover:bg-primary/20 transition-all active:scale-95"
                      >
                        <span className="material-symbols-outlined text-sm">add</span>
                        Add First Animal
                      </Link>
                    </div>
                  </td>
                </tr>
              ) : (
                displayRows.map((r) => (
                  <tr key={r.id} className="group hover:bg-surface-container-high/30 transition-colors">
                    <td className="px-8 py-5">
                      <div className="flex items-center gap-3">
                        {r.profile_photo ? (
                          <img
                            alt={r.id}
                            className="w-8 h-8 rounded-full object-cover border border-primary/20"
                            src={r.profile_photo}
                          />
                        ) : (
                          <span className={`w-2 h-2 rounded-full ${r.dot}`}></span>
                        )}
                        <span className="font-mono text-sm font-bold text-white">{r.id}</span>
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <span className="text-sm text-on-surface/80">{r.gender}</span>
                    </td>
                    <td className="px-6 py-5">
                      <span className="text-sm font-medium text-on-surface/80 whitespace-nowrap">{r.dob}</span>
                    </td>
                    <td className="px-6 py-5">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-slate-500 text-lg">category</span>
                        <span className="text-sm">{r.breed}</span>
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full ${
                          statusStyles[r.status.color].pill
                        } text-[10px] font-bold uppercase tracking-wider`}
                      >
                        <span
                          className={`w-1 h-1 rounded-full ${statusStyles[r.status.color].dot} ${
                            r.status.pulse ? 'animate-pulse' : ''
                          }`}
                        ></span>
                        {r.status.label}
                      </span>
                    </td>
                    <td className="px-8 py-5 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <Link
                          to="/health/animal-profile-bt-8842"
                          className="p-2 text-slate-400 hover:text-primary transition-colors hover:bg-primary/5 rounded-lg"
                        >
                          <span className="material-symbols-outlined text-xl">visibility</span>
                        </Link>
                        <button
                          className="p-2 text-slate-400 hover:text-secondary transition-colors hover:bg-secondary/5 rounded-lg"
                          type="button"
                        >
                          <span className="material-symbols-outlined text-xl">edit</span>
                        </button>
                        <button
                          className="p-2 text-slate-400 hover:text-error transition-colors hover:bg-error/5 rounded-lg"
                          type="button"
                        >
                          <span className="material-symbols-outlined text-xl">delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="px-8 py-4 bg-surface-container-lowest/30 flex items-center justify-between">
          <p className="text-xs text-slate-500 font-medium">
            Showing <span className="text-on-surface">{displayRows.length}</span> of{' '}
            <span className="text-on-surface">{cattleList.length}</span> tracked animals
          </p>
          <div className="flex items-center gap-2">
            <button className="p-1.5 hover:bg-surface-container-high rounded-lg text-slate-400 transition-colors" type="button">
              <span className="material-symbols-outlined text-lg">chevron_left</span>
            </button>
            <div className="flex gap-1">
              <button className="w-8 h-8 rounded-lg bg-primary/10 text-primary text-xs font-bold border border-primary/20" type="button">
                1
              </button>
            </div>
            <button className="p-1.5 hover:bg-surface-container-high rounded-lg text-slate-400 transition-colors" type="button">
              <span className="material-symbols-outlined text-lg">chevron_right</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
