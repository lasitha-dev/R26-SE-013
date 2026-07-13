import React, { useState, useEffect, useContext } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ProfileContext } from '../../../context/ProfileContext'

export default function WellnessDataIntake() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('single') // 'single' or 'bulk'
  
  // Lists state
  const [cattleList, setCattleList] = useState([])
  const [dailyLogsList, setDailyLogsList] = useState([])
  
  // Selected single log form values
  const [selectedCattleId, setSelectedCattleId] = useState('')
  const [selectedCattle, setSelectedCattle] = useState(null)
  
  // Global message states
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  
  // CSV states
  const [csvFileName, setCsvFileName] = useState('')
  const [parsedLogs, setParsedLogs] = useState([])

  // Modal warning triggers (kept for legacy support or bulk modal, but single uses predictionResult)
  const [showAnomalyModal, setShowAnomalyModal] = useState(false)
  const [pendingPayload, setPendingPayload] = useState(null)

  // Edit Log states
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingLog, setEditingLog] = useState(null)
  const [editErrorMessage, setEditErrorMessage] = useState('')

  const { checkAlertsStatus } = useContext(ProfileContext)
  const [predictionResult, setPredictionResult] = useState(null)

  // Default date configuration
  const todayDateString = new Date().toISOString().split('T')[0]

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('token')
      const headers = { Authorization: token ? `Bearer ${token}` : '' }
      
      const [cattleRes, logsRes] = await Promise.all([
        fetch('http://127.0.0.1:8000/api/cattle', { headers }),
        fetch('http://127.0.0.1:8000/api/daily-logs', { headers })
      ])

      if (cattleRes.ok) {
        const cattleData = await cattleRes.json()
        setCattleList(cattleData || [])
      }
      if (logsRes.ok) {
        const logsData = await logsRes.json()
        setDailyLogsList(logsData || [])
      }
    } catch (err) {
      console.error('Error loading dynamic data:', err)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  // Filter dropdown subjects so that ONLY cattle in lactation period (within 305 days of calving) are listed
  const lactationActiveCattle = cattleList.filter((c) => {
    if (!c.calving_date) return false // No calving date means not lactating
    const calvingDate = new Date(c.calving_date)
    const today = new Date()
    calvingDate.setHours(0, 0, 0, 0)
    today.setHours(0, 0, 0, 0)
    
    if (today < calvingDate) return false // Future calving date is not in lactation period
    
    const diffTime = Math.abs(today - calvingDate)
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    return diffDays <= 305
  })

  const handleCattleChange = (e) => {
    const id = e.target.value
    setSelectedCattleId(id)
    const animal = cattleList.find((c) => c.id === id)
    setSelectedCattle(animal || null)
    setPredictionResult(null) // reset prediction banner on subject change
  }

  // ─── Native CSV Parser ───────────────────────────────────────────────────
  const handleCSVUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return

    setCsvFileName(file.name)
    setErrorMessage('')
    setSuccessMessage('')

    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const text = event.target.result
        const lines = text.split('\n').map((l) => l.trim()).filter((l) => l.length > 0)
        
        if (lines.length < 2) {
          throw new Error('CSV file is empty or has no data rows.')
        }

        // Headers check
        const headers = lines[0].split(',').map((h) => h.trim().toLowerCase())
        const cattleIdIdx = headers.indexOf('cattle_id')
        const dateIdx = headers.indexOf('date')
        const milkYieldIdx = headers.indexOf('milk_yield')
        const weightIdx = headers.indexOf('weight')

        if (cattleIdIdx === -1 || dateIdx === -1 || milkYieldIdx === -1 || weightIdx === -1) {
          throw new Error('Invalid CSV headers. Required: cattle_id, date, milk_yield, weight')
        }

        const logs = []
        for (let i = 1; i < lines.length; i++) {
          const cols = lines[i].split(',').map((c) => c.trim())
          if (cols.length < headers.length) continue

          const milkYield = parseFloat(cols[milkYieldIdx])
          const weight = parseFloat(cols[weightIdx])

          if (isNaN(milkYield) || isNaN(weight) || milkYield < 0 || weight < 0.1) {
            throw new Error(`Data validation error at row ${i + 1}. Weight (min 0.1) and Milk (min 0) must be positive values.`)
          }

          logs.push({
            cattle_id: cols[cattleIdIdx],
            date: cols[dateIdx],
            milk_yield: milkYield,
            weight: weight
          })
        }

        setParsedLogs(logs)
        setSuccessMessage(`Successfully parsed ${logs.length} data entries. Ready to upload.`)
      } catch (err) {
        setErrorMessage(err.message || 'Error parsing CSV file.')
        setCsvFileName('')
        setParsedLogs([])
      }
    }
    reader.readAsText(file)
  }

  // ─── POST/PUT Logic Helpers ──────────────────────────────────────────────
  const postDailyLog = async (payload) => {
    const token = localStorage.getItem('token')
    const response = await fetch('http://127.0.0.1:8000/api/daily-logs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify(payload),
    })
    return response
  }

  // ─── Derived Features Helpers ───────────────────────────────────────────
  const calculateAgeMonths = (dobStr) => {
    if (!dobStr) return 0
    const dob = new Date(dobStr)
    const today = new Date()
    return (today.getFullYear() - dob.getFullYear()) * 12 + (today.getMonth() - dob.getMonth())
  }

  const getDaysInMilk = (calvingDateStr, loggingDateStr) => {
    if (!calvingDateStr) return 0
    const calving = new Date(calvingDateStr)
    const logDate = new Date(loggingDateStr)
    calving.setHours(0, 0, 0, 0)
    logDate.setHours(0, 0, 0, 0)
    const diffTime = logDate - calving
    if (diffTime < 0) return 0
    return Math.floor(diffTime / (1000 * 60 * 60 * 24))
  }

  const getLactationStage = (dim) => {
    if (dim <= 100) return 'Early'
    if (dim <= 200) return 'Mid'
    return 'Late'
  }

  const getHistoricalMetrics = (cattleId, loggingDateStr, currentMilk, currentWeight) => {
    const logDate = new Date(loggingDateStr)
    
    const cattleLogs = dailyLogsList
      .filter((l) => l.cattle_id === cattleId)
      .sort((a, b) => new Date(b.date) - new Date(a.date))
      
    // Previous Week Avg (7 days prior to logging date)
    const sevenDaysAgo = new Date(logDate)
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
    
    const weekLogs = cattleLogs.filter((l) => {
      const d = new Date(l.date)
      return d >= sevenDaysAgo && d < logDate
    })
    
    const prevWeekAvg = weekLogs.length > 0 
      ? weekLogs.reduce((sum, l) => sum + l.milk_yield, 0) / weekLogs.length 
      : currentMilk
      
    // Day_Minus_3 (exactly 3 days ago)
    const targetDate3DaysAgo = new Date(logDate)
    targetDate3DaysAgo.setDate(targetDate3DaysAgo.getDate() - 3)
    const targetDate3Str = targetDate3DaysAgo.toISOString().split('T')[0]
    
    const day3Log = cattleLogs.find((l) => l.date === targetDate3Str)
    
    const dayMinus3Milk = day3Log ? day3Log.milk_yield : currentMilk
    const dayMinus3Weight = day3Log ? day3Log.weight : currentWeight
    
    return {
      prevWeekAvg,
      dayMinus3Milk,
      dayMinus3Weight
    }
  }

  // ─── Form Submission Handler ─────────────────────────────────────────────
  const handleSubmitSingle = async (e) => {
    e.preventDefault()
    setErrorMessage('')
    setSuccessMessage('')
    setPredictionResult(null)

    const formData = new FormData(e.target)
    const milkYield = parseFloat(formData.get('milk_yield'))
    const weight = parseFloat(formData.get('weight'))
    const dateVal = formData.get('date')

    if (!selectedCattleId || !selectedCattle) {
      setErrorMessage('Please select a subject animal.')
      return
    }

    // Dynamic validations check (Front-end)
    if (isNaN(milkYield) || milkYield < 0) {
      setErrorMessage('Daily Milk Yield must be a positive number or zero.')
      return
    }
    if (isNaN(weight) || weight < 0.1) {
      setErrorMessage('Body weight must be a positive number greater than or equal to 0.1 KG.')
      return
    }

    // Calculate dynamic derived metrics
    const ageMonths = calculateAgeMonths(selectedCattle.dob)
    const daysInMilk = getDaysInMilk(selectedCattle.calving_date, dateVal)
    const lactationStage = getLactationStage(daysInMilk)

    // Calculate historical attributes or fall back to current values
    const hist = getHistoricalMetrics(selectedCattleId, dateVal, milkYield, weight)

    // Build the prediction payload
    const predictPayload = {
      cattle_id: selectedCattleId,
      Breed: selectedCattle.breed,
      Age_Months: parseInt(ageMonths, 10),
      Weight_kg: parseFloat(weight),
      Milk_Yield_L: parseFloat(milkYield),
      Days_in_Milk: parseInt(daysInMilk, 10),
      Lactation_Stage: lactationStage,
      Previous_Week_Avg_Yield: parseFloat(hist.prevWeekAvg),
      Day_Minus_3_Milk: parseFloat(hist.dayMinus3Milk),
      Day_Minus_3_Weight: parseFloat(hist.dayMinus3Weight)
    }

    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      
      // 1. Post to predict API
      const predictRes = await fetch('http://127.0.0.1:8000/api/monitor/predict', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(predictPayload)
      })

      if (!predictRes.ok) {
        throw new Error('Prediction service failed to respond.')
      }

      const predictData = await predictRes.json()

      // 2. Post to save daily log API to ensure database persistence
      const logPayload = {
        cattle_id: selectedCattleId,
        date: dateVal,
        milk_yield: milkYield,
        weight: weight
      }
      const saveRes = await postDailyLog(logPayload)

      if (saveRes.ok) {
        setPredictionResult(predictData)
        if (predictData.is_anomaly) {
          setErrorMessage('Potential health issue detected. Please initiate the 7-Day Triage.')
        } else {
          setSuccessMessage('Data Updated Successfully. Health status is normal.')
        }
        await checkAlertsStatus() // Sync global alerts notification count/status
        fetchData() // Refresh logs list
      } else {
        const errData = await saveRes.json()
        setErrorMessage(errData.detail || 'Failed to save daily log details.')
      }

    } catch (err) {
      setErrorMessage(err.message || 'Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  // ─── Bulk Submit Handler ─────────────────────────────────────────────────
  const handleBulkSubmit = async () => {
    if (parsedLogs.length === 0) return

    setLoading(true)
    setErrorMessage('')
    setSuccessMessage('')

    const token = localStorage.getItem('token')
    try {
      const response = await fetch('http://127.0.0.1:8000/api/daily-logs/bulk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(parsedLogs),
      })
      const data = await response.json()
      if (response.ok) {
        setSuccessMessage(data.message || `Bulk upload completed successfully.`)
        setParsedLogs([])
        setCsvFileName('')
        fetchData() // Refresh logs list
      } else {
        setErrorMessage(data.detail || 'Bulk upload failed.')
      }
    } catch (err) {
      setErrorMessage('Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  // ─── Anomaly Modal Actions (Bulk backup) ──────────────────────────────────
  const handleModalTriage = async () => {
    if (!pendingPayload) return
    setLoading(true)
    await postDailyLog(pendingPayload)
    setLoading(false)
    setShowAnomalyModal(false)
    navigate('/health/7-day-triage-scan')
  }

  const handleModalDismiss = async () => {
    if (!pendingPayload) return
    setLoading(true)
    await postDailyLog(pendingPayload)
    setLoading(false)
    setShowAnomalyModal(false)
    fetchData()
  }

  // ─── Edit Daily Log Actions ──────────────────────────────────────────────
  const openEditLogModal = (log) => {
    setEditingLog(log)
    setEditErrorMessage('')
    setShowEditModal(true)
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    setEditErrorMessage('')

    const formData = new FormData(e.target)
    const milkYield = parseFloat(formData.get('edit_milk_yield'))
    const weight = parseFloat(formData.get('edit_weight'))
    const dateVal = formData.get('edit_date')
    const cattleId = formData.get('edit_cattle_id')

    if (isNaN(milkYield) || milkYield < 0) {
      setEditErrorMessage('Daily Milk Yield must be a positive number or zero.')
      return
    }
    if (isNaN(weight) || weight < 0.1) {
      setEditErrorMessage('Body Weight must be a positive number greater than or equal to 0.1 KG.')
      return
    }

    const payload = {
      cattle_id: cattleId,
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
        setShowEditModal(false)
        setSuccessMessage('Daily log updated successfully.')
        fetchData()
      } else {
        const data = await response.json()
        setEditErrorMessage(data.detail || 'Failed to update daily log entry.')
      }
    } catch (err) {
      setEditErrorMessage('Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex justify-center min-h-[calc(100vh-8rem)]">
      <div className="max-w-4xl w-full space-y-12">
        {/* Main intake card container */}
        <div className="bg-surface-container-high rounded-2xl p-6 md:p-10 border border-outline-variant/10 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <span className="material-symbols-outlined text-[150px] text-primary">edit_note</span>
          </div>

          <div className="relative space-y-8">
            <header>
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
              <h2 className="text-3xl font-black text-white tracking-tight uppercase">Wellness Data Intake</h2>
              <p className="text-sm text-slate-400 mt-2 font-medium">
                Log clinical vital signs and daily metrics for early diagnostics. Only lactating cows (calving period &lt; 305 days) are listed for daily log entries.
              </p>
            </header>

            {/* Tab Switcher */}
            <div className="flex border-b border-white/5 gap-2">
              <button
                className={`pb-4 px-4 font-bold text-sm tracking-wide uppercase transition-all border-b-2 ${
                  activeTab === 'single'
                    ? 'text-primary border-primary'
                    : 'text-slate-400 border-transparent hover:text-white'
                }`}
                onClick={() => {
                  setActiveTab('single')
                  setErrorMessage('')
                  setSuccessMessage('')
                  setPredictionResult(null)
                }}
                type="button"
              >
                Single Log Entry
              </button>
              <button
                className={`pb-4 px-4 font-bold text-sm tracking-wide uppercase transition-all border-b-2 ${
                  activeTab === 'bulk'
                    ? 'text-primary border-primary'
                    : 'text-slate-400 border-transparent hover:text-white'
                }`}
                onClick={() => {
                  setActiveTab('bulk')
                  setErrorMessage('')
                  setSuccessMessage('')
                  setPredictionResult(null)
                }}
                type="button"
              >
                Bulk Upload CSV
              </button>
            </div>

            {errorMessage && !predictionResult && (
              <div className="p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider">
                {errorMessage}
              </div>
            )}

            {successMessage && !predictionResult && (
              <div className="p-4 bg-primary/10 border border-primary/20 text-primary rounded-lg text-xs font-bold uppercase tracking-wider">
                {successMessage}
              </div>
            )}

            {/* Single Log Entry Tab */}
            {activeTab === 'single' && (
              <form className="space-y-6" onSubmit={handleSubmitSingle}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Select Subject */}
                  <div className="space-y-2">
                    <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                      Select Subject (Only Lactating Cows)
                    </label>
                    <div className="relative">
                      <select
                        className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-base font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                        value={selectedCattleId}
                        onChange={handleCattleChange}
                        required
                      >
                        <option disabled value="">
                          Choose Bovine Unit
                        </option>
                        {lactationActiveCattle.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.identifier} ({c.breed}) - Day {Math.ceil(Math.abs(new Date() - new Date(c.calving_date)) / (1000 * 60 * 60 * 24))}
                          </option>
                        ))}
                      </select>
                      <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                        expand_more
                      </span>
                    </div>
                  </div>

                  {/* Date Input */}
                  <div className="space-y-2">
                    <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                      Logging Date
                    </label>
                    <input
                      defaultValue={todayDateString}
                      className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-base font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all [color-scheme:dark]"
                      name="date"
                      required
                      type="date"
                      max={todayDateString}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Daily Milk Yield */}
                  <div className="space-y-2">
                    <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                      Daily Milk Yield (Liters)
                    </label>
                    <div className="relative">
                      <input
                        className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-2xl font-display font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                        placeholder="0.0"
                        name="milk_yield"
                        type="number"
                        step="0.1"
                        min="0"
                        required
                      />
                      <span className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-600 font-bold">
                        LITERS
                      </span>
                    </div>
                  </div>

                  {/* Weight Input */}
                  <div className="space-y-2">
                    <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                      Body Weight Before Milking (kg)
                    </label>
                    <div className="relative">
                      <input
                        className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-2xl font-display font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                        placeholder="0.00"
                        name="weight"
                        type="number"
                        step="0.01"
                        min="0.1"
                        required
                      />
                      <span className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-600 font-bold">
                        KG
                      </span>
                    </div>
                  </div>
                </div>



                <div className="bg-primary-container/5 border border-primary-container/10 rounded-lg p-4 flex items-start gap-4">
                  <span
                    className="material-symbols-outlined text-primary mt-0.5"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    info
                  </span>
                  <p className="text-sm text-primary-container font-medium leading-relaxed">
                    Continuous daily logging enables the AI to detect sub-clinical health anomalies early.
                    <span className="text-[10px] block mt-1 text-primary/60 font-normal uppercase tracking-widest">
                      Protocol: VET-SEC-09
                    </span>
                  </p>
                </div>

                <button
                  className="w-full h-16 rounded-xl bg-gradient-to-br from-primary-container to-primary text-on-primary-container font-black text-lg tracking-[0.2em] uppercase shadow-xl shadow-primary/20 hover:scale-[1.01] active:scale-[0.98] transition-all flex items-center justify-center gap-3 disabled:opacity-50"
                  type="submit"
                  disabled={loading}
                >
                  <span>{loading ? 'Processing Prediction...' : 'Update Yield'}</span>
                  <span className="material-symbols-outlined">send</span>
                </button>

                {/* AI Prediction Outcome Banner */}
                {predictionResult && (
                  <div className="pt-2">
                    {predictionResult.is_anomaly ? (
                      <div className="p-6 bg-error/15 border border-error/30 text-error rounded-xl flex flex-col items-center gap-4 text-center">
                        <p className="font-bold text-sm">
                          🚨 ALERT: Potential health issue detected. Please initiate the 7-Day Triage.
                        </p>
                        <Link
                          to="/health/7-day-triage-scan"
                          className="px-6 py-2.5 bg-error text-on-error text-xs font-bold uppercase tracking-wider rounded-lg hover:bg-error/95 transition-all"
                        >
                          Start 7-Day Diagnosis
                        </Link>
                      </div>
                    ) : (
                      <div className="p-4 bg-primary/10 border border-primary/20 text-primary rounded-lg text-xs font-bold uppercase tracking-wider text-center">
                        ✅ Data Updated Successfully. Health status is normal.
                      </div>
                    )}
                  </div>
                )}
              </form>
            )}

            {/* Bulk Upload CSV Tab */}
            {activeTab === 'bulk' && (
              <div className="space-y-6">
                <div className="border-2 border-dashed border-white/10 rounded-xl p-8 flex flex-col items-center justify-center text-center bg-surface-container-lowest/50 hover:border-primary/30 transition-colors relative group">
                  <span className="material-symbols-outlined text-5xl text-slate-500 group-hover:text-primary transition-colors mb-3">
                    upload_file
                  </span>
                  <p className="text-sm text-white font-bold mb-1">
                    {csvFileName || 'Select or Drag CSV File'}
                  </p>
                  <p className="text-xs text-slate-500 max-w-sm mb-4 leading-relaxed">
                    Ensure your file contains these columns: <code className="text-primary font-mono font-bold">cattle_id</code>, <code className="text-primary font-mono font-bold">date</code>, <code className="text-primary font-mono font-bold">milk_yield</code>, <code className="text-primary font-mono font-bold">weight</code>
                  </p>
                  
                  <input
                    accept=".csv"
                    className="hidden"
                    id="csv-file-upload"
                    onChange={handleCSVUpload}
                    type="file"
                  />
                  <label
                    htmlFor="csv-file-upload"
                    className="px-5 py-2.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/25 rounded-lg text-xs font-bold uppercase tracking-widest cursor-pointer transition-all active:scale-95"
                  >
                    Browse File
                  </label>
                </div>

                <div className="bg-surface-container-low p-5 rounded-lg border border-white/5 space-y-2">
                  <h4 className="text-xs font-black text-slate-400 tracking-widest uppercase">CSV File Schema Format</h4>
                  <pre className="text-xs font-mono text-slate-500 overflow-x-auto bg-surface-container-lowest p-3 rounded border border-white/5">
                    {"cattle_id,date,milk_yield,weight\n6a525de0a16...,2026-07-11,28.5,340.2\nmock-8842,2026-07-11,4.2,650.0"}
                  </pre>
                </div>

                <button
                  className="w-full h-16 rounded-xl bg-gradient-to-br from-primary-container to-primary text-on-primary-container font-black text-lg tracking-[0.2em] uppercase shadow-xl shadow-primary/20 hover:scale-[1.01] active:scale-[0.98] transition-all flex items-center justify-center gap-3 disabled:opacity-50"
                  onClick={handleBulkSubmit}
                  disabled={loading || parsedLogs.length === 0}
                  type="button"
                >
                  <span>{loading ? 'Uploading Data...' : 'Import Bulk Data'}</span>
                  <span className="material-symbols-outlined">cloud_upload</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Daily Logs Table */}
        <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden shadow-2xl">
          <div className="px-8 py-5 border-b border-white/5">
            <h3 className="text-base font-bold text-white tracking-tight uppercase">Daily Logs Registry</h3>
            <p className="text-xs text-slate-500 mt-0.5">Edit or audit recorded daily dairy yield and weights</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-container-lowest/50 text-slate-400 text-[10px] uppercase tracking-[0.2em] font-bold">
                  <th className="px-8 py-4">Subject (Cattle)</th>
                  <th className="px-8 py-4">Date</th>
                  <th className="px-8 py-4">Milk Yield</th>
                  <th className="px-8 py-4">Body Weight</th>
                  <th className="px-8 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {dailyLogsList.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="px-8 py-10 text-center text-xs text-slate-500 font-bold uppercase tracking-wider">
                      No logs recorded yet.
                    </td>
                  </tr>
                ) : (
                  dailyLogsList.map((log) => {
                    const animal = cattleList.find((c) => c.id === log.cattle_id)
                    return (
                      <tr key={log.id} className="hover:bg-surface-container-high/30 transition-colors">
                        <td className="px-8 py-4 font-bold text-white text-sm">
                          {animal ? animal.identifier : log.cattle_id}
                        </td>
                        <td className="px-8 py-4 font-mono text-sm text-slate-400">{log.date}</td>
                        <td className="px-8 py-4 text-sm text-primary font-semibold">{log.milk_yield} L</td>
                        <td className="px-8 py-4 text-sm text-secondary font-semibold">{log.weight} KG</td>
                        <td className="px-8 py-4 text-right">
                          <button
                            onClick={() => openEditLogModal(log)}
                            className="px-3 py-1.5 bg-primary/10 border border-primary/20 text-primary text-xs font-bold rounded hover:bg-primary/20 transition-all active:scale-95"
                          >
                            Edit
                          </button>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Anomaly Warning Modal */}
      {showAnomalyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/80 backdrop-blur-md">
          <div className="bg-[#171f33] border border-error/20 rounded-xl p-8 max-w-md w-full shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-error to-transparent"></div>
            <div className="flex flex-col items-center text-center">
              <div className="w-16 h-16 rounded-full bg-error/15 border border-error/30 flex items-center justify-center mb-6 relative">
                <span className="material-symbols-outlined text-4xl text-error animate-pulse">
                  warning
                </span>
              </div>
              <h3 className="text-xl font-black text-white tracking-tight uppercase mb-4">
                Clinical Anomaly Detected!
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-8">
                Statistical anomaly detected! We recommend initiating a 7-Day Deep Diagnostic triage window for this animal.
              </p>
              <div className="w-full flex flex-col gap-3">
                <button
                  onClick={handleModalTriage}
                  className="w-full py-3.5 bg-error text-on-error font-black text-xs uppercase tracking-wider rounded-lg hover:bg-error/90 active:scale-95 transition-all flex items-center justify-center gap-2"
                  type="button"
                >
                  <span className="material-symbols-outlined text-base">emergency_home</span>
                  Start 7-Day Diagnosis
                </button>
                <button
                  onClick={handleModalDismiss}
                  className="w-full py-3.5 bg-surface-container-high hover:bg-surface-bright text-slate-300 text-xs font-bold uppercase tracking-wider rounded-lg border border-white/5 active:scale-95 transition-all"
                  type="button"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Daily Log Modal */}
      {showEditModal && editingLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/80 backdrop-blur-md">
          <div className="bg-[#171f33] border border-outline-variant/10 rounded-xl p-8 max-w-md w-full shadow-2xl relative overflow-hidden">
            <h3 className="text-xl font-black text-white tracking-tight uppercase mb-6">
              Edit Daily Log Entry
            </h3>

            {editErrorMessage && (
              <div className="mb-4 p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider">
                {editErrorMessage}
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="space-y-4">
              <input type="hidden" name="edit_cattle_id" defaultValue={editingLog.cattle_id} />
              
              {/* Date */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  Logging Date
                </label>
                <input
                  defaultValue={editingLog.date}
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all [color-scheme:dark]"
                  name="edit_date"
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
                  name="edit_milk_yield"
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
                  name="edit_weight"
                  required
                  type="number"
                  step="0.01"
                  min="0.1"
                />
              </div>

              <div className="pt-6 flex justify-between gap-4">
                <button
                  onClick={() => setShowEditModal(false)}
                  className="px-6 py-3 bg-surface-container-high hover:bg-surface-bright text-slate-300 text-xs font-bold uppercase rounded-lg border border-white/5 transition-all"
                  type="button"
                >
                  Cancel
                </button>
                <button
                  className="px-8 py-3 bg-primary hover:opacity-90 text-on-primary font-black text-xs uppercase tracking-wider rounded-lg transition-all"
                  type="submit"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
