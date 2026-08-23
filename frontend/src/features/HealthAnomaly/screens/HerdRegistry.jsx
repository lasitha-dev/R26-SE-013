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

  // Static mock rows as fallback demo data
  const mockRows = [
    {
      id: 'mock-8842',
      identifier: '#BT-8842',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '2020-05-12 (4 Yrs, 2 Mos)',
      breed: 'Friesian',
      status: { label: 'Healthy', color: 'Healthy', pulse: false },
      profile_photo: null,
    },
    {
      id: 'mock-sudu',
      identifier: 'Sudu',
      dot: 'bg-error',
      gender: 'Male',
      dob: '2021-01-05 (3 Yrs, 6 Mos)',
      breed: 'Jersey',
      status: { label: 'At Risk', color: 'At Risk', pulse: true },
      profile_photo: null,
    },
    {
      id: 'mock-7729',
      identifier: '#BT-7729',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '2019-10-20 (5 Yrs)',
      breed: 'Sahiwal',
      status: { label: 'Healthy', color: 'Healthy', pulse: false },
      profile_photo: null,
    },
    {
      id: 'mock-maanam',
      identifier: 'Maanam',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '2022-03-15 (2 Yrs, 4 Mos)',
      breed: 'Local',
      status: { label: 'Healthy', color: 'Healthy', pulse: false },
      profile_photo: null,
    },
  ]

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

  useEffect(() => {
    fetchCattle()
  }, [])

  const handleDeleteCattle = async (cattleId) => {
    if (cattleId.startsWith('mock-')) {
      alert('Mock records cannot be deleted.')
      return
    }
    if (
      !window.confirm(
        'Are you sure you want to delete this animal and all its associated logs? This action cannot be undone.'
      )
    ) {
      return
    }
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`http://127.0.0.1:8000/api/cattle/${cattleId}`, {
        method: 'DELETE',
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
        },
      })
      if (response.ok) {
        // Refresh registry list
        fetchCattle()
      } else {
        alert('Failed to delete cattle record.')
      }
    } catch (err) {
      alert('Error connecting to backend during deletion.')
    } finally {
      setLoading(false)
    }
  }

  // ─── Dynamic Top Statistics ────────────────────────────────────────────────
  const totalLivestock = cattleList.length
  const healthyCount = cattleList.filter((c) => (c.health_status || c.status || 'Healthy') === 'Healthy').length
  const pendingAlertsCount = cattleList.filter((c) => (c.health_status || c.status || 'Healthy') !== 'Healthy').length

  const bioSecurityScore =
    totalLivestock > 0 ? Math.round((healthyCount / totalLivestock) * 100) : 100

  // ─── Dynamic Breed Composition ─────────────────────────────────────────────
  const dynamicBreeds = React.useMemo(() => {
    const sourceList = cattleList.length > 0 ? cattleList : mockRows
    if (!sourceList || sourceList.length === 0) return []

    const breedCounts = {}
    sourceList.forEach((animal) => {
      const breedName = animal.breed ? animal.breed.trim() : 'Unknown'
      breedCounts[breedName] = (breedCounts[breedName] || 0) + 1
    })

    const sortedBreeds = Object.entries(breedCounts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 4)

    const themeColors = [
      { color: 'bg-primary', textCls: 'text-primary' },
      { color: 'bg-secondary', textCls: 'text-secondary' },
      { color: 'bg-tertiary', textCls: 'text-tertiary' },
      { color: 'bg-primary-container', textCls: 'text-primary-container' },
    ]

    const total = sourceList.length
    return sortedBreeds.map((b, idx) => ({
      name: b.name,
      count: b.count,
      percentage: total > 0 ? Math.round((b.count / total) * 100) : 0,
      color: themeColors[idx % themeColors.length].color,
      textCls: themeColors[idx % themeColors.length].textCls,
    }))
  }, [cattleList, mockRows])

  // ─── Dynamic Population Health Trends (BCS Distribution Bar Chart) ────────
  const bcsBuckets = React.useMemo(() => {
    const sourceList = cattleList.length > 0 ? cattleList : mockRows
    const buckets = [
      { label: '<2.5', count: 0 },
      { label: '2.5-2.9', count: 0 },
      { label: '3.0-3.4', count: 0 },
      { label: '3.5-3.9', count: 0 },
      { label: '4.0-4.4', count: 0 },
      { label: '≥4.5', count: 0 },
    ]

    let scoredCount = 0
    sourceList.forEach((c) => {
      const score = c.bcs_score !== undefined && c.bcs_score !== null ? Number(c.bcs_score) : null
      if (score !== null && !isNaN(score)) {
        scoredCount++
        if (score < 2.5) buckets[0].count++
        else if (score < 3.0) buckets[1].count++
        else if (score < 3.5) buckets[2].count++
        else if (score < 4.0) buckets[3].count++
        else if (score < 4.5) buckets[4].count++
        else buckets[5].count++
      }
    })

    // If no explicit BCS scores exist in dataset, construct distribution from health status
    if (scoredCount === 0) {
      const total = sourceList.length || 1
      const healthy = sourceList.filter((c) => (c.health_status || c.status || 'Healthy') === 'Healthy').length
      const atRisk = Math.max(0, total - healthy)

      buckets[0].count = atRisk
      buckets[2].count = Math.floor(healthy * 0.4)
      buckets[3].count = Math.ceil(healthy * 0.6)
    }

    const maxCount = Math.max(...buckets.map((b) => b.count), 1)

    return buckets.map((b) => ({
      ...b,
      heightPct: Math.max(15, Math.round((b.count / maxCount) * 100)),
    }))
  }, [cattleList, mockRows])

  const maxBucketIdx = React.useMemo(() => {
    let maxIdx = 0
    let maxVal = -1
    bcsBuckets.forEach((b, idx) => {
      if (b.count > maxVal) {
        maxVal = b.count
        maxIdx = idx
      }
    })
    return maxIdx
  }, [bcsBuckets])

  // Map API cattle array to table rows
  const displayRows =
    cattleList.length > 0
      ? cattleList.map((c) => {
          const rawStatus = c.health_status || c.status || 'Healthy'
          const isHealthy = rawStatus === 'Healthy'
          return {
            id: c.id,
            identifier: c.identifier,
            dot: isHealthy ? 'bg-primary' : 'bg-error',
            gender: c.gender,
            dob: `${c.dob} (${calculateAge(c.dob)})`,
            breed: c.breed,
            status: {
              label: isHealthy ? 'Healthy' : 'Alert',
              color: isHealthy ? 'Healthy' : 'At Risk',
              pulse: !isHealthy,
            },
            profile_photo: c.profile_photo,
          }
        })
      : mockRows

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
        <div className="col-span-12 lg:col-span-8 bg-surface-container-low rounded-xl p-6 relative overflow-hidden group flex flex-col justify-between">
          <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
            <span className="material-symbols-outlined text-[120px] text-primary">analytics</span>
          </div>
          <div className="relative z-10">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest">
                Population Health Trends (BCS Spread)
              </h3>
              <span className="text-[10px] text-slate-500 font-mono uppercase font-bold">
                {totalLivestock} Animals Evaluated
              </span>
            </div>
            <div className="flex items-end gap-3 h-36 px-2 pb-6 border-b border-white/5">
              {bcsBuckets.map((bucket, idx) => {
                const isMax = idx === maxBucketIdx
                return (
                  <div key={idx} className="flex-1 flex flex-col items-center h-full justify-end relative group/bar">
                    {isMax && (
                      <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-surface text-primary text-[10px] font-bold px-2 py-0.5 rounded border border-primary/20 whitespace-nowrap shadow-md z-20">
                        OPT-MAX
                      </div>
                    )}
                    <div
                      className={`w-full rounded-t transition-all duration-500 ${
                        isMax ? 'bg-primary hover:bg-primary/80' : 'bg-primary/20 hover:bg-primary/40'
                      }`}
                      style={{ height: `${bucket.heightPct}%` }}
                      title={`${bucket.label}: ${bucket.count} animals`}
                    ></div>
                    <span className="absolute -bottom-5 text-[9px] font-semibold text-slate-400">
                      {bucket.label}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 bg-surface-container-low rounded-xl p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Breed Composition</h3>
            <p className="text-xs text-slate-500">Distribution analysis across primary herds</p>
          </div>
          <div className="space-y-3 mt-4">
            {dynamicBreeds.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-4">No breed data available.</p>
            ) : (
              dynamicBreeds.map((b) => (
                <div key={b.name} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-300">{b.name}</span>
                    <span className={`text-xs font-bold ${b.textCls}`}>
                      {b.percentage}% ({b.count})
                    </span>
                  </div>
                  <div className="w-full h-1 bg-surface rounded-full overflow-hidden">
                    <div
                      className={`h-full ${b.color} transition-all duration-500`}
                      style={{ width: `${b.percentage}%` }}
                    ></div>
                  </div>
                </div>
              ))
            )}
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
                            alt={r.identifier}
                            className="w-8 h-8 rounded-full object-cover border border-primary/20 flex-shrink-0"
                            src={r.profile_photo}
                          />
                        ) : (
                          <div className="w-8 h-8 rounded-full bg-surface-container-highest flex items-center justify-center border border-white/5 flex-shrink-0">
                            <span className="material-symbols-outlined text-sm text-slate-500">pets</span>
                          </div>
                        )}
                        <span className="font-mono text-sm font-bold text-white">{r.identifier}</span>
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
                          to={`/health/animal-profile/${r.id}`}
                          className="p-2 text-slate-400 hover:text-primary transition-colors hover:bg-primary/5 rounded-lg"
                        >
                          <span className="material-symbols-outlined text-xl">visibility</span>
                        </Link>
                        <Link
                          to={`/health/animal-profile/${r.id}`}
                          className="p-2 text-slate-400 hover:text-secondary transition-colors hover:bg-secondary/5 rounded-lg"
                        >
                          <span className="material-symbols-outlined text-xl">edit</span>
                        </Link>
                        <button
                          onClick={() => handleDeleteCattle(r.id)}
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
