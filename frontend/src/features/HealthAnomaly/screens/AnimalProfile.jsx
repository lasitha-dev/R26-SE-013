import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { calculateAge } from './AddNewAnimal.jsx'

export default function AnimalProfile() {
  const { id } = useParams()
  const [cattle, setCattle] = useState(null)
  const [dailyLogs, setDailyLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Edit Cattle Modal states
  const [showEditCattleModal, setShowEditCattleModal] = useState(false)
  const [editErrorMessage, setEditErrorMessage] = useState('')

  // Edit Log Modal states
  const [showEditLogModal, setShowEditLogModal] = useState(false)
  const [editingLog, setEditingLog] = useState(null)
  const [editLogErrorMessage, setEditLogErrorMessage] = useState('')

  // Default date configurations
  const todayDateString = new Date().toISOString().split('T')[0]

  const fetchCattleAndLogs = async () => {
    try {
      const token = localStorage.getItem('token')
      const headers = { Authorization: token ? `Bearer ${token}` : '' }

      const [cattleRes, logsRes] = await Promise.all([
        fetch(`http://127.0.0.1:8000/api/cattle/${id}`, { headers }),
        fetch(`http://127.0.0.1:8000/api/cattle/${id}/daily-logs`, { headers })
      ])

      if (cattleRes.ok && logsRes.ok) {
        const cattleData = await cattleRes.json()
        const logsData = await logsRes.json()
        setCattle(cattleData)
        setDailyLogs(logsData || [])
      } else {
        setError('Failed to load profile details.')
      }
    } catch (err) {
      setError('Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCattleAndLogs()
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-10rem)]">
        <div className="flex flex-col items-center gap-3">
          <span className="material-symbols-outlined text-5xl text-primary animate-spin">
            progress_activity
          </span>
          <p className="font-bold tracking-wider uppercase text-xs text-slate-400">
            Loading Profile...
          </p>
        </div>
      </div>
    )
  }

  if (error || !cattle) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-10rem)]">
        <div className="bg-surface-container-high rounded-xl p-8 border border-error/20 text-center max-w-sm">
          <span className="material-symbols-outlined text-5xl text-error mb-2">
            warning
          </span>
          <p className="font-black text-white uppercase tracking-tight text-lg mb-2">
            Error Loading Profile
          </p>
          <p className="text-sm text-slate-400 mb-6">{error || 'Animal record not found.'}</p>
          <Link
            to="/health/herd-registry"
            className="px-6 py-2.5 bg-primary text-on-primary text-xs font-bold rounded-lg uppercase tracking-wider"
          >
            Back to Registry
          </Link>
        </div>
      </div>
    )
  }

  const getLactationStage = (calvingDateStr) => {
    if (!calvingDateStr) return 'N/A'
    const calvingDate = new Date(calvingDateStr)
    const today = new Date()
    
    // Reset time components
    calvingDate.setHours(0, 0, 0, 0)
    today.setHours(0, 0, 0, 0)
    
    if (today < calvingDate) {
      return 'Pre-Calving'
    }
    
    const diffTime = Math.abs(today - calvingDate)
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    
    if (diffDays <= 100) {
      return `Early (Day ${diffDays})`
    } else if (diffDays <= 200) {
      return `Mid (Day ${diffDays})`
    } else if (diffDays <= 305) {
      return `Late (Day ${diffDays})`
    } else {
      return `Dry Period (Day ${diffDays})`
    }
  }

  const ageString = calculateAge(cattle.dob)

  // Get last 7 daily logs for chart trends
  const displayLogs = dailyLogs.slice(-7)

  // Milk yield metrics
  const maxMilk = Math.max(...displayLogs.map((l) => l.milk_yield), 10)
  const avgYield =
    dailyLogs.length > 0
      ? (dailyLogs.reduce((acc, l) => acc + l.milk_yield, 0) / dailyLogs.length).toFixed(1)
      : 0

  // Weight metrics
  const maxWeight = Math.max(...displayLogs.map((l) => l.weight), 100)

  // Edit details form submit handler
  const handleEditCattleSubmit = async (e) => {
    e.preventDefault()
    setEditErrorMessage('')

    const formData = new FormData(e.target)
    const identifier = formData.get('edit_identifier')
    const breed = formData.get('edit_breed')
    const gender = formData.get('edit_gender')
    const weightVal = formData.get('edit_weight')
    const dob = formData.get('edit_dob')
    const calvingDateVal = formData.get('edit_calving_date')

    if (!identifier || !breed || !gender || !weightVal || !dob) {
      setEditErrorMessage('Please fill in all required fields.')
      return
    }

    const weight = parseFloat(weightVal)
    if (isNaN(weight) || weight < 0.1) {
      setEditErrorMessage('Weight must be a positive number greater than or equal to 0.1 KG.')
      return
    }

    const dobDate = new Date(dob)
    const today = new Date()
    dobDate.setHours(0, 0, 0, 0)
    today.setHours(0, 0, 0, 0)

    if (dobDate > today) {
      setEditErrorMessage('Date of Birth cannot be in the future.')
      return
    }

    if (calvingDateVal) {
      const calvingDate = new Date(calvingDateVal)
      calvingDate.setHours(0, 0, 0, 0)
      if (calvingDate > today) {
        setEditErrorMessage('Calving Date cannot be in the future.')
        return
      }
      if (calvingDate < dobDate) {
        setEditErrorMessage('Calving Date cannot be before the Date of Birth.')
        return
      }
    }

    const payload = {
      identifier: identifier.trim(),
      gender,
      dob,
      breed,
      weight,
      profile_photo: cattle.profile_photo || null,
      calving_date: calvingDateVal || null,
      status: cattle.status
    }

    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`http://127.0.0.1:8000/api/cattle/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(payload),
      })
      if (response.ok) {
        setShowEditCattleModal(false)
        fetchCattleAndLogs() // Refresh profile details
      } else {
        const data = await response.json()
        setEditErrorMessage(data.detail || 'Failed to update details.')
      }
    } catch (err) {
      setEditErrorMessage('Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  // Edit Log submit handler
  const handleEditLogSubmit = async (e) => {
    e.preventDefault()
    setEditLogErrorMessage('')

    const formData = new FormData(e.target)
    const milkYield = parseFloat(formData.get('edit_log_milk_yield'))
    const weight = parseFloat(formData.get('edit_log_weight'))
    const dateVal = formData.get('edit_log_date')

    if (isNaN(milkYield) || milkYield < 0) {
      setEditLogErrorMessage('Milk Yield must be a positive number or zero.')
      return
    }
    if (isNaN(weight) || weight < 0.1) {
      setEditLogErrorMessage('Weight must be a positive number greater than or equal to 0.1 KG.')
      return
    }

    const payload = {
      cattle_id: id,
      date: dateVal,
      milk_yield: milkYield,
      weight: weight
    }

    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`http://127.0.0.1:8000/api/daily-logs/${editingLog.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(payload),
      })
      if (response.ok) {
        setShowEditLogModal(false)
        fetchCattleAndLogs()
      } else {
        const data = await response.json()
        setEditLogErrorMessage(data.detail || 'Failed to update daily log entry.')
      }
    } catch (err) {
      setEditLogErrorMessage('Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  // Delete log handler
  const handleDeleteLog = async (logId) => {
    if (!window.confirm('Are you sure you want to delete this daily log entry?')) {
      return
    }
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`http://127.0.0.1:8000/api/daily-logs/${logId}`, {
        method: 'DELETE',
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
        },
      })
      if (response.ok) {
        fetchCattleAndLogs()
      } else {
        alert('Failed to delete log entry.')
      }
    } catch (err) {
      alert('Error connecting to backend during deletion.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Back Button and Title Area */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link
              to="/health/herd-registry"
              className="flex items-center gap-1 text-primary-fixed uppercase text-[10px] font-black tracking-[0.3em] hover:underline"
            >
              <span className="material-symbols-outlined text-xs">arrow_back</span>
              Back to Registry
            </Link>
            <div className="h-px w-12 bg-outline-variant/30"></div>
          </div>
          <h1 className="text-4xl font-black text-on-surface tracking-tighter uppercase">
            ANIMAL PROFILE: {cattle.identifier}
          </h1>
          <div className="flex flex-wrap gap-2 mt-4">
            {[cattle.breed, cattle.gender, ageString].map((t) => (
              <span
                key={t}
                className="px-3 py-1 bg-surface-container-highest text-on-surface text-[10px] font-bold tracking-widest rounded uppercase"
              >
                {t}
              </span>
            ))}
            <span
              className={`px-3 py-1 ${
                cattle.status === 'Healthy'
                  ? 'bg-primary-container/20 text-primary border-primary/30'
                  : 'bg-error-container/20 text-error border-error/30'
              } text-[10px] font-black tracking-widest rounded border uppercase flex items-center gap-1.5`}
            >
              <span
                className={`w-1.5 h-1.5 ${
                  cattle.status === 'Healthy' ? 'bg-primary' : 'bg-error'
                } rounded-full animate-pulse`}
              ></span>
              {cattle.status}
            </span>
          </div>
        </div>
        <div className="flex gap-4">
          <button
            className="px-5 py-2.5 bg-surface-container-highest hover:bg-surface-bright text-primary text-xs font-bold rounded-lg transition-all border border-primary/10"
            type="button"
            aria-label="Secondary action"
          >
            <span className="material-symbols-outlined text-base">download</span>
          </button>
          <button
            onClick={() => setShowEditCattleModal(true)}
            className="px-5 py-2.5 bg-primary hover:opacity-90 text-on-primary text-xs font-bold rounded-lg transition-all shadow-lg shadow-primary/20"
            type="button"
          >
            Edit Details
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Visual State & Photo */}
        <div className="col-span-12 lg:col-span-5 bg-surface-container-low rounded-lg overflow-hidden border border-outline-variant/10">
          <div className="relative h-64 bg-surface-container-lowest flex items-center justify-center overflow-hidden">
            {cattle.profile_photo ? (
              <img
                alt={`${cattle.identifier} profile`}
                className="w-full h-full object-cover opacity-80"
                src={cattle.profile_photo}
              />
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 text-slate-500">
                <span className="material-symbols-outlined text-7xl" style={{ fontVariationSettings: "'wght' 100" }}>
                  pets
                </span>
                <span className="text-[10px] font-bold tracking-widest uppercase text-slate-600">
                  No Image Available
                </span>
              </div>
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-surface-container-low via-transparent to-transparent"></div>
            <div className="absolute bottom-6 left-6 right-6 flex items-center justify-between">
              <div>
                <p className="text-[10px] uppercase font-black tracking-widest text-slate-400">Owner Assigned Tag</p>
                <h2 className="text-2xl font-black text-white">{cattle.identifier}</h2>
              </div>
              <div className="flex gap-2">
                <span className="material-symbols-outlined text-primary text-2xl">sensors</span>
                <span className="material-symbols-outlined text-primary text-2xl">visibility</span>
              </div>
            </div>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">Core Parameters</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-surface-container rounded-lg border border-white/5">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Weight</span>
                  <p className="text-xl font-bold mt-1 text-white">{cattle.weight} KG</p>
                </div>
                <div className="p-4 bg-surface-container rounded-lg border border-white/5">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Lactation Stage</span>
                  <p className="text-xl font-bold mt-1 text-white">{getLactationStage(cattle.calving_date)}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Analytics & Metrics */}
        <div className="col-span-12 lg:col-span-7 space-y-6">
          {/* Milk Yield Chart Card */}
          <div className="bg-surface-container-low rounded-lg p-6 border border-outline-variant/10">
            <div className="flex justify-between items-center mb-6">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Milk Yield Analytics</h3>
                <p className="text-xs text-slate-500">Weekly tracking and peak yield points</p>
              </div>
              <span className="px-3 py-1 bg-primary/10 text-primary text-[10px] font-bold tracking-widest rounded-full uppercase">
                Avg: {avgYield}L / Day
              </span>
            </div>
            
            {displayLogs.length === 0 ? (
              <div className="h-36 flex items-center justify-center border border-dashed border-white/5 rounded">
                <span className="text-xs text-slate-500 uppercase tracking-wider font-bold">
                  No milk yield records found
                </span>
              </div>
            ) : (
              <div>
                <div className="flex items-end gap-2 h-36 px-2 border-b border-outline-variant/20 pb-2">
                  {displayLogs.map((log, idx) => {
                    const pct = (log.milk_yield / maxMilk) * 100
                    return (
                      <div key={log.id || idx} className="w-full flex flex-col justify-end h-full group/bar relative">
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/bar:block bg-surface-container-highest border border-primary/20 text-primary text-[10px] font-bold px-2.5 py-1 rounded whitespace-nowrap z-20 shadow-xl">
                          {log.milk_yield} L ({log.date})
                        </div>
                        <div
                          className="w-full rounded-t bg-primary/30 hover:bg-primary transition-all duration-300 cursor-pointer"
                          style={{ height: `${pct}%` }}
                        ></div>
                      </div>
                    )
                  })}
                </div>
                <div className="flex justify-between text-[8px] sm:text-[10px] text-slate-500 font-semibold tracking-wider uppercase mt-4 px-2 overflow-x-auto whitespace-nowrap gap-1">
                  {displayLogs.map((log, idx) => (
                    <span key={log.id || idx} className="flex-1 text-center">
                      {log.date.slice(5)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Daily Body Weight Trend Card */}
          <div className="bg-surface-container-low rounded-lg p-6 border border-outline-variant/10">
            <div className="flex justify-between items-center mb-6">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Body Weight Trend</h3>
                <p className="text-xs text-slate-500">Weight logs trend monitor (KG)</p>
              </div>
              <span className="px-3 py-1 bg-secondary/10 text-secondary text-[10px] font-bold tracking-widest rounded-full uppercase">
                Active Monitor
              </span>
            </div>

            {displayLogs.length === 0 ? (
              <div className="h-36 flex items-center justify-center border border-dashed border-white/5 rounded">
                <span className="text-xs text-slate-500 uppercase tracking-wider font-bold">
                  No body weight records found
                </span>
              </div>
            ) : (
              <div>
                <div className="flex items-end gap-2 h-36 px-2 border-b border-outline-variant/20 pb-2">
                  {displayLogs.map((log, idx) => {
                    const pct = (log.weight / maxWeight) * 100
                    return (
                      <div key={log.id || idx} className="w-full flex flex-col justify-end h-full group/bar relative">
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/bar:block bg-surface-container-highest border border-secondary/20 text-secondary text-[10px] font-bold px-2.5 py-1 rounded whitespace-nowrap z-20 shadow-xl">
                          {log.weight} KG ({log.date})
                        </div>
                        <div
                          className="w-full rounded-t bg-secondary/30 hover:bg-secondary transition-all duration-300 cursor-pointer"
                          style={{ height: `${pct}%` }}
                        ></div>
                      </div>
                    )
                  })}
                </div>
                <div className="flex justify-between text-[8px] sm:text-[10px] text-slate-500 font-semibold tracking-wider uppercase mt-4 px-2 overflow-x-auto whitespace-nowrap gap-1">
                  {displayLogs.map((log, idx) => (
                    <span key={log.id || idx} className="flex-1 text-center">
                      {log.date.slice(5)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* BCS Trend Info */}
          <div className="bg-surface-container-low rounded-lg p-6 border border-outline-variant/10">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Body Condition Score (BCS) Trend</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-surface-container rounded-lg border border-white/5 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Current Score</span>
                <p className="text-2xl font-black text-primary mt-2">3.75</p>
                <span className="text-[10px] text-slate-400 mt-1">Normal / Healthy</span>
              </div>
              <div className="p-4 bg-surface-container rounded-lg border border-white/5 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Last Scored</span>
                <p className="text-2xl font-black text-slate-300 mt-2">3.50</p>
                <span className="text-[10px] text-slate-400 mt-1">12-May-2024</span>
              </div>
              <div className="p-4 bg-surface-container rounded-lg border border-white/5 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">AI Confidence</span>
                <p className="text-2xl font-black text-secondary mt-2">94%</p>
                <span className="text-[10px] text-slate-400 mt-1">Sentinel Vision</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dynamic Animal Specific Daily Logs Table */}
      <div className="bg-surface-container-low rounded-lg border border-outline-variant/10 overflow-hidden shadow-2xl">
        <div className="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight uppercase">Daily Health & Yield Logs</h3>
            <p className="text-xs text-slate-500 mt-0.5">Recorded metrics for this subject animal</p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-lowest/50 text-slate-400 text-[10px] uppercase tracking-[0.2em] font-bold">
                <th className="px-8 py-4">Date</th>
                <th className="px-8 py-4">Daily Milk Yield</th>
                <th className="px-8 py-4">Body Weight</th>
                <th className="px-8 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {dailyLogs.length === 0 ? (
                <tr>
                  <td colSpan="4" className="px-8 py-10 text-center text-xs text-slate-500 font-bold uppercase tracking-wider">
                    No records found
                  </td>
                </tr>
              ) : (
                dailyLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-surface-container-high/40 transition-colors">
                    <td className="px-8 py-4 text-sm text-on-surface/80 font-mono">{log.date}</td>
                    <td className="px-8 py-4 text-sm font-semibold text-primary">{log.milk_yield} L</td>
                    <td className="px-8 py-4 text-sm font-semibold text-secondary">{log.weight} KG</td>
                    <td className="px-8 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => {
                            setEditingLog(log)
                            setEditLogErrorMessage('')
                            setShowEditLogModal(true)
                          }}
                          className="px-3 py-1 bg-primary/10 border border-primary/20 text-primary text-xs font-bold rounded hover:bg-primary/20 transition-all active:scale-95"
                          type="button"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteLog(log.id)}
                          className="px-3 py-1 bg-error/10 border border-error/20 text-error text-xs font-bold rounded hover:bg-error/20 transition-all active:scale-95"
                          type="button"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Historical Assessment Log */}
      <div className="bg-surface-container-low rounded-lg border border-outline-variant/10 overflow-hidden">
        <div className="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight uppercase">Historical Assessment Log</h3>
            <p className="text-xs text-slate-500 mt-0.5">Clinical diagnostics & surveillance record</p>
          </div>
          <button className="px-4 py-2 bg-surface-container hover:bg-surface-container-high text-xs font-bold rounded-lg border border-outline-variant/10 transition-all text-slate-300">
            Export Records
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-lowest/50 text-slate-400 text-[10px] uppercase tracking-[0.2em] font-bold">
                <th className="px-8 py-4">Date</th>
                <th className="px-8 py-4">Assessment Type</th>
                <th className="px-8 py-4">Result / Score</th>
                <th className="px-8 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {[
                {
                  date: 'Oct 24, 2023',
                  iconBg: 'bg-secondary-container/20',
                  iconColor: 'text-secondary',
                  icon: 'psychology',
                  type: 'AI BCS Analysis',
                  resultClass: 'bg-primary/10 text-primary',
                  result: 'Score: 3.75 (Normal)',
                },
                {
                  date: 'Sep 12, 2023',
                  iconBg: 'bg-on-tertiary-fixed-variant/20',
                  iconColor: 'text-tertiary',
                  icon: 'health_and_safety',
                  type: 'Manual Vet Exam',
                  resultClass: 'bg-primary/10 text-primary',
                  result: 'Normal Physiological State',
                },
                {
                  date: 'Aug 05, 2023',
                  iconBg: 'bg-error-container/20',
                  iconColor: 'text-error',
                  icon: 'warning',
                  type: 'Predictive Fever Detection',
                  resultClass: 'bg-error/10 text-error',
                  result: 'Mild Metabolic Heat Stress',
                },
              ].map((log, idx) => (
                <tr key={idx} className="hover:bg-surface-container-high/40 transition-colors">
                  <td className="px-8 py-4 text-sm text-on-surface/80 font-mono">{log.date}</td>
                  <td className="px-8 py-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full ${log.iconBg} ${log.iconColor} flex items-center justify-center flex-shrink-0`}>
                        <span className="material-symbols-outlined text-lg">{log.icon}</span>
                      </div>
                      <span className="text-sm font-semibold">{log.type}</span>
                    </div>
                  </td>
                  <td className="px-8 py-4">
                    <span className={`inline-block px-2.5 py-0.5 rounded text-xs font-bold ${log.resultClass}`}>
                      {log.result}
                    </span>
                  </td>
                  <td className="px-8 py-4 text-right">
                    <button className="text-slate-500 hover:text-primary transition-colors text-xs font-bold uppercase tracking-wider">
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─── Edit Cattle Details Modal ──────────────────────────────────────── */}
      {showEditCattleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/80 backdrop-blur-md">
          <div className="bg-[#171f33] border border-outline-variant/10 rounded-xl p-8 max-w-md w-full shadow-2xl relative overflow-hidden">
            <h3 className="text-xl font-black text-white tracking-tight uppercase mb-6">
              Edit Cattle Profile Details
            </h3>

            {editErrorMessage && (
              <div className="mb-4 p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider">
                {editErrorMessage}
              </div>
            )}

            <form onSubmit={handleEditCattleSubmit} className="space-y-4">
              {/* Identifier */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Identifier (Tag ID / Name)
                </label>
                <input
                  defaultValue={cattle.identifier}
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                  name="edit_identifier"
                  required
                  type="text"
                />
              </div>

              {/* Gender and Breed */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                    Gender
                  </label>
                  <select
                    defaultValue={cattle.gender}
                    className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                    name="edit_gender"
                    required
                  >
                    <option value="Female">Female</option>
                    <option value="Male">Male</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                    Breed
                  </label>
                  <select
                    defaultValue={cattle.breed}
                    className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                    name="edit_breed"
                    required
                  >
                    <option value="Jersey">Jersey</option>
                    <option value="Friesian">Friesian</option>
                    <option value="Sahiwal">Sahiwal</option>
                    <option value="Local">Local</option>
                  </select>
                </div>
              </div>

              {/* DOB */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Date of Birth (DOB)
                </label>
                <input
                  defaultValue={cattle.dob}
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all [color-scheme:dark]"
                  name="edit_dob"
                  required
                  type="date"
                  max={todayDateString}
                />
              </div>

              {/* Calving Date */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Last Calving Date (Optional)
                </label>
                <input
                  defaultValue={cattle.calving_date || ''}
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all [color-scheme:dark]"
                  name="edit_calving_date"
                  type="date"
                  max={todayDateString}
                />
              </div>

              {/* Weight */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Body Weight (KG)
                </label>
                <input
                  defaultValue={cattle.weight}
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                  name="edit_weight"
                  required
                  type="number"
                  step="0.01"
                  min="0.1"
                />
              </div>

              <div className="pt-6 flex justify-between gap-4">
                <button
                  onClick={() => setShowEditCattleModal(false)}
                  className="px-6 py-3 bg-surface-container-high hover:bg-surface-bright text-slate-300 text-xs font-bold uppercase rounded-lg border border-white/5 transition-all"
                  type="button"
                >
                  Cancel
                </button>
                <button
                  className="px-8 py-3 bg-primary hover:opacity-90 text-on-primary font-black text-xs uppercase tracking-wider rounded-lg transition-all"
                  type="submit"
                >
                  Save Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── Edit Daily Log Modal ──────────────────────────────────────────── */}
      {showEditLogModal && editingLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/80 backdrop-blur-md">
          <div className="bg-[#171f33] border border-outline-variant/10 rounded-xl p-8 max-w-md w-full shadow-2xl relative overflow-hidden">
            <h3 className="text-xl font-black text-white tracking-tight uppercase mb-6">
              Edit Daily Log Entry
            </h3>

            {editLogErrorMessage && (
              <div className="mb-4 p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider">
                {editLogErrorMessage}
              </div>
            )}

            <form onSubmit={handleEditLogSubmit} className="space-y-4">
              {/* Date */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Logging Date
                </label>
                <input
                  defaultValue={editingLog.date}
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all [color-scheme:dark]"
                  name="edit_log_date"
                  required
                  type="date"
                  max={todayDateString}
                />
              </div>

              {/* Milk Yield */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Daily Milk Yield (Liters)
                </label>
                <input
                  defaultValue={editingLog.milk_yield}
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                  name="edit_log_milk_yield"
                  required
                  type="number"
                  step="0.1"
                  min="0"
                />
              </div>

              {/* Weight */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Body Weight (KG)
                </label>
                <input
                  defaultValue={editingLog.weight}
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                  name="edit_log_weight"
                  required
                  type="number"
                  step="0.01"
                  min="0.1"
                />
              </div>

              <div className="pt-6 flex justify-between gap-4">
                <button
                  onClick={() => setShowEditLogModal(false)}
                  className="px-6 py-3 bg-surface-container-high hover:bg-surface-bright text-slate-300 text-xs font-bold uppercase rounded-lg border border-white/5 transition-all"
                  type="button"
                >
                  Cancel
                </button>
                <button
                  className="px-8 py-3 bg-primary hover:opacity-90 text-on-primary font-black text-xs uppercase tracking-wider rounded-lg transition-all"
                  type="submit"
                >
                  Save Log
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
