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
  const [bulkReportResults, setBulkReportResults] = useState(null)

  // Modal warning triggers (pops up when anomaly is detected upon submission)
  const [showAnomalyModal, setShowAnomalyModal] = useState(false)

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

  // ─── Dynamic Sample CSV Generator ─────────────────────────────────────────
  const downloadSampleCSV = () => {
    const todayStr = new Date().toISOString().split('T')[0]
    let sampleCows = lactationActiveCattle.length > 0 ? lactationActiveCattle : cattleList
    if (sampleCows.length === 0) {
      sampleCows = [
        { identifier: 'kiri katiya', breed: 'Jersey' },
        { identifier: 'sudu putha', breed: 'Holstein-Friesian' }
      ]
    }

    const headers = 'identifier,date,milk_yield,weight\n'
    const rows = sampleCows.slice(0, 5).map((cow) => {
      const defaultMilk = cow.breed === 'Jersey' ? 14.5 : (cow.breed === 'Holstein-Friesian' ? 22.0 : 12.0)
      const defaultWeight = cow.breed === 'Jersey' ? 410.0 : 550.0
      return `${cow.identifier},${todayStr},${defaultMilk},${defaultWeight}`
    }).join('\n')

    const csvContent = 'data:text/csv;charset=utf-8,' + encodeURIComponent(headers + rows + '\n')
    const downloadAnchor = document.createElement('a')
    downloadAnchor.setAttribute('href', csvContent)
    downloadAnchor.setAttribute('download', `sample_dairy_intake_${todayStr}.csv`)
    document.body.appendChild(downloadAnchor)
    downloadAnchor.click()
    downloadAnchor.remove()
  }

  // ─── Native CSV Parser ───────────────────────────────────────────────────
  const handleCSVUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return

    setCsvFileName(file.name)
    setErrorMessage('')
    setSuccessMessage('')
    setBulkReportResults(null)

    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const text = event.target.result
        const lines = text.split('\n').map((l) => l.trim()).filter((l) => l.length > 0)
        
        if (lines.length < 2) {
          throw new Error('CSV file is empty or has no data rows.')
        }

        // Headers check (case-insensitive and trimmed)
        const headers = lines[0].split(',').map((h) => h.trim().toLowerCase().replace(/['"]+/g, ''))
        
        const cattleIdIdx = headers.findIndex((h) => ['cattle_id', 'cattleid', 'id'].includes(h))
        const identifierIdx = headers.findIndex((h) => ['identifier', 'tag', 'cow', 'name', 'cow_id'].includes(h))
        
        if (cattleIdIdx === -1 && identifierIdx === -1) {
          throw new Error('Invalid CSV headers. Either "identifier" (cow tag/name) or "cattle_id" column is required.')
        }

        const dateIdx = headers.findIndex((h) => ['date', 'log_date', 'logging_date'].includes(h))
        const milkYieldIdx = headers.findIndex((h) => ['milk_yield', 'milk', 'yield', 'milk_yield_l'].includes(h))
        const weightIdx = headers.findIndex((h) => ['weight', 'wt', 'weight_kg', 'body_weight'].includes(h))

        if (dateIdx === -1 || milkYieldIdx === -1 || weightIdx === -1) {
          throw new Error('Invalid CSV headers. Required: (identifier or cattle_id), date, milk_yield, weight')
        }

        // Optional headers
        const waterIdx = headers.findIndex((h) => ['water_intake', 'water'].includes(h))
        const feedIdx = headers.findIndex((h) => ['feed_intake', 'feed'].includes(h))
        const tempIdx = headers.findIndex((h) => ['body_temp', 'temp', 'temperature'].includes(h))

        const logs = []
        for (let i = 1; i < lines.length; i++) {
          const cols = lines[i].split(',').map((c) => c.trim().replace(/^["']|["']$/g, ''))
          if (cols.length < 3 || cols.every((c) => c === '')) continue

          const milkYield = parseFloat(cols[milkYieldIdx])
          const weight = parseFloat(cols[weightIdx])

          if (isNaN(milkYield) || isNaN(weight) || milkYield < 0 || weight < 0.1) {
            throw new Error(`Data validation error at row ${i + 1}. Weight (min 0.1) and Milk (min 0) must be positive values.`)
          }

          const logItem = {
            date: cols[dateIdx],
            milk_yield: milkYield,
            weight: weight
          }

          if (identifierIdx !== -1 && cols[identifierIdx]) {
            logItem.identifier = cols[identifierIdx]
          }
          if (cattleIdIdx !== -1 && cols[cattleIdIdx]) {
            logItem.cattle_id = cols[cattleIdIdx]
          }

          if (!logItem.cattle_id && !logItem.identifier) {
            throw new Error(`Row ${i + 1} is missing both cattle identifier and cattle_id.`)
          }

          if (waterIdx !== -1 && cols[waterIdx]) {
            const w = parseFloat(cols[waterIdx])
            if (!isNaN(w)) logItem.water_intake = w
          }
          if (feedIdx !== -1 && cols[feedIdx]) {
            const f = parseFloat(cols[feedIdx])
            if (!isNaN(f)) logItem.feed_intake = f
          }
          if (tempIdx !== -1 && cols[tempIdx]) {
            const t = parseFloat(cols[tempIdx])
            if (!isNaN(t)) logItem.body_temp = t
          }

          logs.push(logItem)
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

    if (!dateVal) {
      setErrorMessage('Please select a valid intake date.')
      return
    }

    // Duplicate Date Rule (Frontend Prevention)
    const existingLog = dailyLogsList.find(
      (l) =>
        (String(l.cattle_id) === String(selectedCattleId) ||
         (selectedCattle.identifier && String(l.identifier) === String(selectedCattle.identifier))) &&
        String(l.date) === String(dateVal)
    )
    if (existingLog) {
      setErrorMessage(
        `A daily log already exists for "${selectedCattle.identifier}" on ${dateVal}. To enter new data for this date, please delete the existing entry from the Daily Logs Registry below first.`
      )
      return
    }

    // Dynamic validations check (Front-end)
    if (selectedCattle && selectedCattle.calving_date && dateVal < selectedCattle.calving_date) {
      setErrorMessage(`Logging date cannot be prior to the cow's milking start date (${selectedCattle.calving_date}).`)
      return
    }

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
        const errJson = await predictRes.json().catch(() => ({}))
        throw new Error(errJson.detail || 'Prediction service failed to respond.')
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
          setShowAnomalyModal(true)
          setErrorMessage('Potential health issue detected. Please initiate the 7-Day Triage.')
        } else {
          setSuccessMessage('Data Updated Successfully. Health status is normal.')
        }
        await checkAlertsStatus() // Sync global alerts notification count/status
        await fetchData() // Refresh logs list
      } else {
        const errData = await saveRes.json().catch(() => ({}))
        setErrorMessage(errData.detail || 'Failed to save daily log details.')
      }

    } catch (err) {
      setErrorMessage(err.message || 'Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  // ─── Delete Log Handler ──────────────────────────────────────────────────
  const handleDeleteLog = async (logId) => {
    if (!window.confirm('Are you sure you want to delete this daily log entry?')) {
      return
    }
    setLoading(true)
    setErrorMessage('')
    setSuccessMessage('')
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`http://127.0.0.1:8000/api/daily-logs/${logId}`, {
        method: 'DELETE',
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
        },
      })
      if (response.ok) {
        setSuccessMessage('Daily log entry deleted successfully.')
        await checkAlertsStatus()
        await fetchData()
      } else {
        const errJson = await response.json().catch(() => ({}))
        setErrorMessage(errJson.detail || 'Failed to delete daily log entry.')
      }
    } catch (err) {
      setErrorMessage(err.message || 'Error connecting to backend during deletion.')
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
    setBulkReportResults(null)

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
        if (data.results && Array.isArray(data.results)) {
          setBulkReportResults(data)
        }
        setParsedLogs([])
        setCsvFileName('')
        if (checkAlertsStatus) {
          await checkAlertsStatus()
        }
        fetchData() // Refresh logs list and cattle
      } else {
        setErrorMessage(data.detail || 'Bulk upload failed.')
      }
    } catch (err) {
      setErrorMessage('Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  // ─── Anomaly Modal Actions ────────────────────────────────────────────────
  const handleModalTriage = () => {
    setShowAnomalyModal(false)
    if (selectedCattleId) {
      navigate(`/health/7-day-triage-scan?cattle_id=${selectedCattleId}`, {
        state: { cattleId: selectedCattleId }
      })
    } else {
      navigate('/health/7-day-triage-scan')
    }
  }

  const handleModalDismiss = () => {
    setShowAnomalyModal(false)
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

    const editCattle = cattleList.find(c => c.id === cattleId)
    if (editCattle && editCattle.calving_date && dateVal < editCattle.calving_date) {
      setEditErrorMessage(`Logging date cannot be prior to the cow's milking start date (${editCattle.calving_date}).`)
      return
    }

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
                      min={selectedCattle ? selectedCattle.calving_date : undefined}
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
                          to={selectedCattleId ? `/health/7-day-triage-scan?cattle_id=${selectedCattleId}` : '/health/7-day-triage-scan'}
                          state={{ cattleId: selectedCattleId }}
                          className="px-6 py-2.5 bg-error text-on-error text-xs font-bold uppercase tracking-wider rounded-lg hover:bg-error/95 transition-all inline-flex items-center gap-1.5"
                        >
                          <span>Start 7-Day Diagnosis</span>
                          <span className="material-symbols-outlined text-xs">arrow_forward</span>
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
                {/* Automated Batch Monitoring Report (Rendered at the Top) */}
                {bulkReportResults && (
                  <div className="bg-surface-container-low border border-primary/25 rounded-xl p-6 space-y-5 animate-fadeIn shadow-2xl">
                    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/5 pb-4">
                      <div className="flex items-center gap-3">
                        <span className="p-2.5 rounded-xl bg-primary/15 text-primary material-symbols-outlined text-2xl">
                          analytics
                        </span>
                        <div>
                          <h4 className="text-base font-black text-white tracking-tight uppercase font-headline">
                            Automated Batch Monitoring Report
                          </h4>
                          <p className="text-xs text-slate-400">
                            Random Forest persistent monitoring predictions & updated MongoDB herd health statuses
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="px-3 py-1.5 bg-surface-container-lowest text-slate-300 rounded-lg text-xs font-semibold border border-white/5">
                          Ingested: <strong className="text-white font-mono">{bulkReportResults.inserted_count}</strong>
                        </span>
                        <span className="px-3 py-1.5 bg-surface-container-lowest text-slate-300 rounded-lg text-xs font-semibold border border-white/5">
                          Evaluated: <strong className="text-white font-mono">{bulkReportResults.evaluated_count}</strong>
                        </span>
                        <span className={`px-3 py-1.5 rounded-lg text-xs font-black border uppercase tracking-wider ${
                          bulkReportResults.alerts_triggered > 0 
                            ? 'bg-error/20 text-error border-error/30' 
                            : 'bg-[#4edea3]/20 text-[#4edea3] border-[#4edea3]/30'
                        }`}>
                          Alerts: <strong className="font-mono">{bulkReportResults.alerts_triggered}</strong>
                        </span>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="bg-surface-container-lowest/60 text-slate-400 text-[10px] uppercase tracking-[0.15em] font-bold">
                            <th className="px-4 py-3">Cow Identifier</th>
                            <th className="px-4 py-3">Breed</th>
                            <th className="px-4 py-3">Latest Date</th>
                            <th className="px-4 py-3 text-right">Milk (L)</th>
                            <th className="px-4 py-3 text-right">Weight (KG)</th>
                            <th className="px-4 py-3 text-center">Prediction</th>
                            <th className="px-4 py-3 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-xs">
                          {bulkReportResults.results && bulkReportResults.results.map((res, idx) => (
                            <tr key={idx} className="hover:bg-surface-container-high/30 transition-colors">
                              <td className="px-4 py-3.5 font-bold text-white">
                                {res.identifier || res.cattle_id}
                                {res.identifier && res.cattle_id && (
                                  <span className="block text-[10px] text-slate-500 font-mono font-normal">
                                    {res.cattle_id}
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-3.5 text-slate-300">{res.breed}</td>
                              <td className="px-4 py-3.5 font-mono text-slate-400">{res.date}</td>
                              <td className="px-4 py-3.5 text-right font-mono font-bold text-white">
                                {typeof res.milk_yield === 'number' ? res.milk_yield.toFixed(1) : res.milk_yield} L
                              </td>
                              <td className="px-4 py-3.5 text-right font-mono font-bold text-white">
                                {typeof res.weight === 'number' ? res.weight.toFixed(1) : res.weight} KG
                              </td>
                              <td className="px-4 py-3.5 text-center">
                                {res.is_anomaly ? (
                                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-error/20 text-error border border-error/30 animate-pulse">
                                    <span className="w-1.5 h-1.5 rounded-full bg-error"></span>
                                    • ALERT
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-[#4edea3]/20 text-[#4edea3] border border-[#4edea3]/30">
                                    <span className="w-1.5 h-1.5 rounded-full bg-[#4edea3]"></span>
                                    • HEALTHY
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-3.5 text-right">
                                {res.is_anomaly ? (
                                  <Link
                                    to={`/health/7-day-triage-scan?cattle_id=${res.cattle_id}`}
                                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-error text-on-error hover:bg-error/90 font-black text-[11px] uppercase tracking-wider rounded-lg transition-all shadow-lg hover:scale-105 active:scale-95"
                                  >
                                    <span>Start 7-Day Diagnosis</span>
                                    <span className="material-symbols-outlined text-xs">arrow_forward</span>
                                  </Link>
                                ) : (
                                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                                    Optimal
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-surface-container-low p-4 rounded-xl border border-white/5">
                  <div>
                    <h4 className="text-xs font-black text-white tracking-widest uppercase">
                      Batch Cattle Dairy Intake
                    </h4>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Ingest daily records for your herd. Anomaly detection model automatically evaluates every cow.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={downloadSampleCSV}
                    id="download-sample-csv-btn"
                    className="px-4 py-2 bg-secondary/15 hover:bg-secondary/25 text-secondary border border-secondary/30 rounded-lg text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-all active:scale-95 shadow-sm whitespace-nowrap"
                  >
                    <span className="material-symbols-outlined text-sm">download</span>
                    Download Sample CSV
                  </button>
                </div>

                <div className="border-2 border-dashed border-white/10 rounded-xl p-8 flex flex-col items-center justify-center text-center bg-surface-container-lowest/50 hover:border-primary/30 transition-colors relative group">
                  <span className="material-symbols-outlined text-5xl text-slate-500 group-hover:text-primary transition-colors mb-3">
                    upload_file
                  </span>
                  <p className="text-sm text-white font-bold mb-1">
                    {csvFileName || 'Select or Drag CSV File'}
                  </p>
                  <p className="text-xs text-slate-500 max-w-sm mb-4 leading-relaxed">
                    Supported columns: <code className="text-primary font-mono font-bold">identifier</code> (or <code className="text-primary font-mono font-bold">cattle_id</code>), <code className="text-primary font-mono font-bold">date</code>, <code className="text-primary font-mono font-bold">milk_yield</code>, <code className="text-primary font-mono font-bold">weight</code>
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
                  <h4 className="text-xs font-black text-slate-400 tracking-widest uppercase">CSV Schema Reference</h4>
                  <pre className="text-xs font-mono text-slate-400 overflow-x-auto bg-surface-container-lowest p-3 rounded border border-white/5">
                    {"identifier,date,milk_yield,weight\nkiri katiya,2026-10-14,9.5,380.0\nsudu putha,2026-10-14,15.2,420.0"}
                  </pre>
                  <p className="text-[11px] text-slate-500 italic">
                    Note: Multi-day records in a single CSV are automatically sorted and stored in chronological order.
                  </p>
                </div>

                <button
                  className="w-full h-16 rounded-xl bg-gradient-to-br from-primary-container to-primary text-on-primary-container font-black text-lg tracking-[0.2em] uppercase shadow-xl shadow-primary/20 hover:scale-[1.01] active:scale-[0.98] transition-all flex items-center justify-center gap-3 disabled:opacity-50"
                  onClick={handleBulkSubmit}
                  disabled={loading || parsedLogs.length === 0}
                  type="button"
                >
                  <span>{loading ? 'Processing Batch Inference...' : 'Import Bulk Data'}</span>
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
                  [...dailyLogsList]
                    .sort((a, b) => (b.date || '').localeCompare(a.date || ''))
                    .map((log) => {
                    const animal = cattleList.find((c) => String(c.id) === String(log.cattle_id) || String(c._id) === String(log.cattle_id))
                    return (
                      <tr key={log.id} className="hover:bg-surface-container-high/30 transition-colors">
                        <td className="px-8 py-4 font-bold text-white text-sm">
                          {animal ? animal.identifier : (log.identifier || 'Registered Cattle')}
                        </td>
                        <td className="px-8 py-4 font-mono text-sm text-slate-400">{log.date}</td>
                        <td className="px-8 py-4 text-sm text-primary font-semibold">{log.milk_yield} L</td>
                        <td className="px-8 py-4 text-sm text-secondary font-semibold">{log.weight} KG</td>
                        <td className="px-8 py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => openEditLogModal(log)}
                              className="px-3 py-1.5 bg-primary/10 border border-primary/20 text-primary text-xs font-bold rounded hover:bg-primary/20 transition-all active:scale-95"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteLog(log.id)}
                              className="px-3 py-1.5 bg-error/10 border border-error/20 text-error text-xs font-bold rounded hover:bg-error/20 transition-all active:scale-95 flex items-center gap-1"
                              title="Delete this daily log"
                            >
                              <span className="material-symbols-outlined text-xs">delete</span>
                              Delete
                            </button>
                          </div>
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
                  data-testid="modal-start-triage"
                  onClick={handleModalTriage}
                  className="w-full py-3.5 bg-error text-on-error font-black text-xs uppercase tracking-wider rounded-lg hover:bg-error/90 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer shadow-lg shadow-error/20"
                  type="button"
                >
                  <span className="material-symbols-outlined text-base">emergency_home</span>
                  Start 7-Day Diagnosis
                </button>
                <button
                  data-testid="modal-dismiss"
                  onClick={handleModalDismiss}
                  className="w-full py-3.5 bg-surface-container-high hover:bg-surface-bright text-slate-300 hover:text-white text-xs font-bold uppercase tracking-wider rounded-lg border border-white/10 active:scale-95 transition-all cursor-pointer"
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
                  min={(() => {
                    const editCattleObj = cattleList.find(c => c.id === editingLog.cattle_id)
                    return editCattleObj ? editCattleObj.calving_date : undefined
                  })()}
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
