import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function SevenDayTriageScan() {
  const navigate = useNavigate()

  const [cattleList, setCattleList] = useState([])
  const [imageFile, setImageFile] = useState(null)
  const [selectedCattleId, setSelectedCattleId] = useState('')
  const [currentDate, setCurrentDate] = useState(new Date().toISOString().split('T')[0])
  const [weatherFetched, setWeatherFetched] = useState(false)
  const [weatherData, setWeatherData] = useState(
    Array(7).fill(null).map(() => ({ temp: 31.4, humidity: 78, thi: 82.4 }))
  )
  const [logsData, setLogsData] = useState({
    yields: [28, 27, 29, 28, 26, 28, 30],
    water: [65, 68, 62, 70, 66, 72, 68],
    feed: [14.2, 14.5, 13.8, 14.0, 14.1, 14.3, 14.2],
    temp: [38.5, 38.6, 38.4, 38.5, 38.7, 38.5, 38.5],
    weight: [580, 582, 579, 581, 580, 583, 581],
  })

  const [bcsPreview, setBcsPreview] = useState(null)
  const [bcsUploading, setBcsUploading] = useState(false)
  const [bcsScore, setBcsScore] = useState('')
  const [dragActive, setDragActive] = useState(false)

  useEffect(() => {
    const fetchCattle = async () => {
      try {
        const token = localStorage.getItem('token')
        const headers = { Authorization: token ? `Bearer ${token}` : '' }
        const res = await fetch('http://127.0.0.1:8000/api/cattle', { headers })
        if (res.ok) {
          const data = await res.json()
          setCattleList(data || [])
        }
      } catch (err) {
        console.error('Error fetching cattle:', err)
      }
    }
    fetchCattle()
  }, [])

  // Weather Source Dialog & GPS Info states
  const [isWeatherModalOpen, setIsWeatherModalOpen] = useState(false)
  const [gpsLoading, setGpsLoading] = useState(false)
  const [gpsResult, setGpsResult] = useState(null) // { lat, lon, district }
  const [activeLocation, setActiveLocation] = useState('')

  const handleFetchOptionA = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.")
      return
    }
    setGpsLoading(true)
    setGpsResult(null)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude
        const lon = position.coords.longitude
        
        fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`)
          .then(res => res.json())
          .then(data => {
            const address = data.address || {}
            const district = address.city || address.state_district || address.town || address.suburb || address.village || "Unknown District"
            
            setGpsResult({ lat: lat.toFixed(4), lon: lon.toFixed(4), district })

            // Dynamic date calculation
            const curDate = new Date(currentDate)
            const start = new Date(curDate)
            start.setDate(curDate.getDate() - 6)
            
            const formatDate = (d) => {
              const yyyy = d.getFullYear()
              const mm = String(d.getMonth() + 1).padStart(2, '0')
              const dd = String(d.getDate()).padStart(2, '0')
              return `${yyyy}-${mm}-${dd}`
            }
            const startDate = formatDate(start)
            const endDate = formatDate(curDate)

            // Fetch real weather data from Open-Meteo
            fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&start_date=${startDate}&end_date=${endDate}&hourly=temperature_2m,relative_humidity_2m&timezone=auto`)
              .then(res => res.json())
              .then(weatherDataJson => {
                const hourly = weatherDataJson.hourly || {}
                const temps = hourly.temperature_2m || []
                const humidities = hourly.relative_humidity_2m || []
                
                const realWeather = []
                for (let i = 0; i < 7; i++) {
                  const hourIndex = i * 24 + 12
                  const tempVal = temps[hourIndex] !== undefined ? temps[hourIndex] : (temps[temps.length - 1] || 28.0)
                  const humidityVal = humidities[hourIndex] !== undefined ? humidities[hourIndex] : (humidities[humidities.length - 1] || 75)
                  
                  const temp = parseFloat(tempVal.toFixed(1))
                  const humidity = Math.round(humidityVal)
                  const thi = parseFloat((0.8 * temp + (humidity / 100) * (temp - 14.3) + 46.4).toFixed(1))
                  
                  realWeather.push({ temp, humidity, thi })
                }

                // Brief timeout to let user see coordinates acquired card in UI
                setTimeout(() => {
                  setWeatherData(realWeather)
                  setWeatherFetched(true)
                  setActiveLocation(district)
                  setIsWeatherModalOpen(false)
                  setGpsResult(null)
                  setGpsLoading(false)
                }, 1500)
              })
              .catch(err => {
                console.error(err)
                setGpsLoading(false)
                setGpsResult(null)
                alert("Error fetching weather data from Open-Meteo API.")
              })
          })
          .catch(err => {
            console.error(err)
            setGpsLoading(false)
            alert("Error fetching reverse geocoded district name.")
          })
      },
      (error) => {
        console.error(error)
        setGpsLoading(false)
        alert("GPS Access Denied. Falling back to default registered location.")
        handleFetchOptionB()
      }
    )
  }

  const handleFetchOptionB = () => {
    const lat = parseFloat(localStorage.getItem('registered_farm_lat'))
    const lon = parseFloat(localStorage.getItem('registered_farm_lon'))
    const district = localStorage.getItem('registered_farm_district') || 'Unknown'

    if (isNaN(lat) || isNaN(lon)) {
      alert('Please pin your exact farm location in Settings first.')
      return
    }

    setGpsLoading(true)
    setGpsResult(null)

    // Dynamic date calculation
    const curDate = new Date(currentDate)
    const start = new Date(curDate)
    start.setDate(curDate.getDate() - 6)
    
    const formatDate = (d) => {
      const yyyy = d.getFullYear()
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      return `${yyyy}-${mm}-${dd}`
    }
    const startDate = formatDate(start)
    const endDate = formatDate(curDate)

    // Fetch real weather data from Open-Meteo directly
    fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&start_date=${startDate}&end_date=${endDate}&hourly=temperature_2m,relative_humidity_2m&timezone=auto`)
      .then(res => res.json())
      .then(weatherDataJson => {
        const hourly = weatherDataJson.hourly || {}
        const temps = hourly.temperature_2m || []
        const humidities = hourly.relative_humidity_2m || []
        
        const realWeather = []
        for (let i = 0; i < 7; i++) {
          const hourIndex = i * 24 + 12
          const tempVal = temps[hourIndex] !== undefined ? temps[hourIndex] : (temps[temps.length - 1] || 28.0)
          const humidityVal = humidities[hourIndex] !== undefined ? humidities[hourIndex] : (humidities[humidities.length - 1] || 75)
          
          const temp = parseFloat(tempVal.toFixed(1))
          const humidity = Math.round(humidityVal)
          const thi = parseFloat((0.8 * temp + (humidity / 100) * (temp - 14.3) + 46.4).toFixed(1))
          
          realWeather.push({ temp, humidity, thi })
        }

        setGpsResult({ lat: lat.toFixed(4), lon: lon.toFixed(4), district })

        // Brief timeout to let user see coordinates acquired card in UI
        setTimeout(() => {
          setWeatherData(realWeather)
          setWeatherFetched(true)
          setActiveLocation(district)
          setIsWeatherModalOpen(false)
          setGpsResult(null)
          setGpsLoading(false)
        }, 1500)
      })
      .catch(err => {
        console.error(err)
        setGpsLoading(false)
        setGpsResult(null)
        alert("Error fetching weather data from Open-Meteo API.")
      })
  }

  const handleLogChange = (type, index, val) => {
    const floatVal = parseFloat(val) || 0
    setLogsData((prev) => {
      const arr = [...prev[type]]
      arr[index] = floatVal
      return { ...prev, [type]: arr }
    })
  }

  const handleImageUpload = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setImageFile(file)
      setBcsPreview(URL.createObjectURL(file))
      setBcsScore('')
    }
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      setImageFile(file)
      setBcsPreview(URL.createObjectURL(file))
      setBcsScore('')
    }
  }

  const handleRunDiagnostics = async () => {
    if (!selectedCattleId) {
      alert('Please select a Cattle ID first.')
      return
    }
    if (!imageFile) {
      alert('Please upload a top-down cattle image first.')
      return
    }

    setBcsUploading(true)
    try {
      const activeCattleObj = cattleList.find(c => c.id === selectedCattleId)
      if (!activeCattleObj) {
        alert('Selected cattle not found.')
        return
      }

      // Step 1: Vision (BCS Score & Grad-CAM Heatmap)
      const formData = new FormData()
      formData.append('file', imageFile)
      formData.append('cattle_id', selectedCattleId)
      formData.append('photo_date', currentDate)

      const bcsRes = await fetch('http://127.0.0.1:8000/api/monitor/predict-bcs', {
        method: 'POST',
        body: formData,
      })

      if (!bcsRes.ok) {
        const errorData = await bcsRes.json()
        throw new Error(errorData.detail || 'BCS prediction failed.')
      }

      const bcsData = await bcsRes.json()
      const calculatedBcs = bcsData.bcs_score
      const gradcamImage = bcsData.gradcam_image

      // Step 2: Data Prep & Calculations
      const cur = new Date(currentDate)
      const dob = new Date(activeCattleObj.dob)
      const calving = activeCattleObj.calving_date ? new Date(activeCattleObj.calving_date) : new Date()

      const ageMonths = Math.max(0, Math.floor((cur - dob) / (1000 * 60 * 60 * 24 * 30.44)))
      const daysInMilk = Math.max(0, Math.floor((cur - calving) / (1000 * 60 * 60 * 24)))

      // Map time-series lists
      const ambient_temp = weatherData.map(w => w.temp)
      const humidity = weatherData.map(w => w.humidity)
      const thi = weatherData.map(w => w.thi)
      const body_temp = logsData.temp
      const milk_yield = logsData.yields
      const water_intake = logsData.water
      const feed_intake = logsData.feed
      const weight = logsData.weight

      // Step 3: Fusion (7-day triage prediction)
      const triagePayload = {
        bcs_score: parseFloat(calculatedBcs),
        age_months: parseInt(ageMonths, 10),
        days_in_milk: parseInt(daysInMilk, 10),
        breed: activeCattleObj.breed,
        genetic_group: 'Exotic',
        lactation_stage: daysInMilk <= 100 ? 'Early' : daysInMilk <= 200 ? 'Mid' : 'Late',
        ambient_temp,
        humidity,
        thi,
        body_temp,
        milk_yield,
        water_intake,
        feed_intake,
        weight
      }

      const triageRes = await fetch('http://127.0.0.1:8000/api/monitor/predict-7day', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(triagePayload),
      })

      if (!triageRes.ok) {
        const errorData = await triageRes.json()
        throw new Error(errorData.detail || '7-Day triage prediction failed.')
      }

      const triageData = await triageRes.json()

      // Step 4: Routing
      navigate('/health/ai-wellness-report', {
        state: {
          triageClass: triageData.class,
          bcsScore: calculatedBcs,
          gradcamImage: gradcamImage,
          activeCattle: activeCattleObj
        }
      })

    } catch (err) {
      alert(`Diagnostics Error: ${err.message}`)
    } finally {
      setBcsUploading(false)
    }
  }

  let calculatedAge = 'N/A'
  let calculatedDim = 'N/A'
  let activeCattle = null

  if (selectedCattleId && currentDate) {
    activeCattle = cattleList.find(c => c.id === selectedCattleId)
    if (activeCattle) {
      const cur = new Date(currentDate)
      const dob = new Date(activeCattle.dob)
      const calving = activeCattle.calving_date ? new Date(activeCattle.calving_date) : null

      const diffAgeMonths = Math.max(0, Math.floor((cur - dob) / (1000 * 60 * 60 * 24 * 30.44)))
      calculatedAge = `${diffAgeMonths} Months`

      if (calving) {
        const diffDimDays = Math.max(0, Math.floor((cur - calving) / (1000 * 60 * 60 * 24)))
        calculatedDim = `${diffDimDays} Days`
      } else {
        calculatedDim = 'N/A'
      }
    }
  }

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Title & Phase Indicator */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <Link
            to="/health/dashboard"
            className="flex items-center gap-1 text-primary-fixed uppercase text-[10px] font-black tracking-[0.3em] hover:underline"
          >
            <span className="material-symbols-outlined text-xs">arrow_back</span>
            Back to Dashboard
          </Link>
          <div className="h-px w-12 bg-outline-variant/30"></div>
        </div>
        <p className="text-primary text-xs font-black tracking-[0.3em] uppercase opacity-80 mt-2">
          Phase 01: Diagnostics
        </p>
        <h2 className="text-4xl font-black text-[#4edea3] tracking-tighter uppercase font-headline">
          7-Day Wellness Triage Intake
        </h2>
        <div className="h-1 w-24 bg-gradient-to-r from-primary to-transparent mt-1"></div>
      </div>

      {/* Subject Selector & Metadata Card */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 bg-surface-container-low border border-white/5 rounded-2xl p-6">
        <div className="md:col-span-4 space-y-2">
          <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
            Subject ID (Cattle Selector)
          </label>
          <div className="relative">
            <select
              className="w-full appearance-none bg-[#060e20] border border-white/10 rounded-lg py-3.5 px-4 text-sm font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
              value={selectedCattleId}
              onChange={(e) => setSelectedCattleId(e.target.value)}
            >
              <option value="">-- Choose Cattle ID --</option>
              {cattleList.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.identifier} ({c.breed})
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
              expand_more
            </span>
          </div>
        </div>

        <div className="md:col-span-4 space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
              Current Date (Day 7)
            </label>
            {activeLocation && (
              <span className="px-2 py-0.5 bg-primary/20 text-[9px] font-black text-primary border border-primary/30 rounded uppercase tracking-wider animate-fadeIn">
                Location: {activeLocation}
              </span>
            )}
          </div>
          <input
            type="date"
            className="w-full bg-[#060e20] border border-white/10 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all [color-scheme:dark]"
            value={currentDate}
            onChange={(e) => setCurrentDate(e.target.value)}
            max={new Date().toISOString().split('T')[0]}
          />
        </div>

        <div className="md:col-span-4 flex items-center justify-end">
          <button
            onClick={() => setIsWeatherModalOpen(true)}
            className="w-full md:w-auto px-6 py-3.5 bg-secondary hover:opacity-90 text-on-secondary font-black text-xs uppercase tracking-wider rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg"
          >
            <span className="material-symbols-outlined text-sm">cloud_sync</span>
            Fetch 7-Day Weather
          </button>
        </div>

        {/* Dynamic Badges */}
        {activeCattle && (
          <div className="col-span-12 grid grid-cols-2 md:grid-cols-5 gap-4 pt-4 border-t border-white/5 animate-fadeIn">
            <div className="bg-[#060e20]/60 border border-white/5 rounded-xl p-3 text-center">
              <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Breed</p>
              <p className="text-xs font-bold text-white mt-1 uppercase">{activeCattle.breed}</p>
            </div>
            <div className="bg-[#060e20]/60 border border-white/5 rounded-xl p-3 text-center">
              <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Genetic Group</p>
              <p className="text-xs font-bold text-white mt-1 uppercase">{activeCattle.geneticGroup}</p>
            </div>
            <div className="bg-[#060e20]/60 border border-white/5 rounded-xl p-3 text-center">
              <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Lactation Stage</p>
              <p className="text-xs font-bold text-white mt-1 uppercase">{activeCattle.lactationStage}</p>
            </div>
            <div className="bg-[#060e20]/60 border border-white/5 rounded-xl p-3 text-center">
              <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Age (Months)</p>
              <p className="text-xs font-black text-primary mt-1 uppercase">{calculatedAge}</p>
            </div>
            <div className="bg-[#060e20]/60 border border-white/5 rounded-xl p-3 text-center">
              <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Days In Milk</p>
              <p className="text-xs font-black text-secondary mt-1 uppercase">{calculatedDim}</p>
            </div>
          </div>
        )}
      </div>

      {/* Main Grid: Upload & Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Upload Image Section */}
        <div className="lg:col-span-4 h-full">
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`glass-card rounded-xl p-8 flex flex-col items-center justify-center text-center group border-dashed border-2 transition-all h-full min-h-[400px] relative overflow-hidden ${dragActive ? 'border-primary bg-primary/5' : 'border-primary/20 hover:border-primary/50'
              }`}
          >
            <input
              type="file"
              id="triage-bcs-input"
              className="hidden"
              accept="image/*"
              onChange={handleImageUpload}
            />

            {bcsPreview ? (
              <div className="space-y-4 relative z-10 w-full">
                <img
                  src={bcsPreview}
                  alt="BCS Preview"
                  className="max-h-48 rounded-lg object-cover mx-auto border border-white/10 shadow-lg"
                />

                {bcsUploading ? (
                  <div className="flex flex-col items-center justify-center gap-2">
                    <span className="material-symbols-outlined text-xl text-primary animate-spin">progress_activity</span>
                    <span className="text-[10px] text-primary font-bold uppercase tracking-wider">AI Detecting Hooks &amp; Pins...</span>
                  </div>
                ) : bcsScore ? (
                  <div className="p-4 bg-primary/10 border border-primary/25 rounded-xl text-center">
                    <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">AI Calculated BCS</p>
                    <p className="text-3xl font-black text-primary mt-1">{bcsScore}</p>
                  </div>
                ) : null}

                <label
                  htmlFor="triage-bcs-input"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-surface-container-highest hover:bg-surface-bright text-xs font-bold rounded-lg cursor-pointer transition-all border border-white/5"
                >
                  <span className="material-symbols-outlined text-sm">photo_library</span>
                  Change Image
                </label>
              </div>
            ) : (
              <label htmlFor="triage-bcs-input" className="cursor-pointer space-y-4 w-full h-full flex flex-col items-center justify-center">
                <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <div className="w-20 h-20 rounded-full bg-surface-container-highest flex items-center justify-center mb-4 ring-8 ring-surface-container-low">
                  <span className="material-symbols-outlined text-4xl text-primary">photo_camera</span>
                </div>
                <h3 className="text-xl font-bold text-on-surface mb-2">Upload Top-Down Cattle Image</h3>
                <p className="text-slate-400 text-sm leading-relaxed max-w-[240px]">
                  Instructions: Capture a top-down view directly above the animal. Spine, hooks, and pins should be clearly visible for AI Body Condition Scoring.
                </p>
                <div className="mt-8">
                  <span className="px-3 py-1 bg-surface-container-lowest text-[10px] font-bold text-primary rounded border border-primary/20 uppercase tracking-widest">
                    AI Ready
                  </span>
                </div>
              </label>
            )}
          </div>
        </div>

        {/* Logs Intake Section */}
        <div className="lg:col-span-8">
          <div className="glass-card rounded-xl p-6 h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-secondary">clinical_notes</span>
                <h3 className="text-base font-bold text-on-surface tracking-tight uppercase">
                  7-Day Physiological Logs
                </h3>
              </div>
              {weatherFetched && (
                <span className="px-2 py-1 bg-secondary/15 text-[9px] font-black text-secondary border border-secondary/20 rounded uppercase tracking-wider animate-pulse">
                  Weather Synced
                </span>
              )}
            </div>

            <div className="flex-1 overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="py-3 px-2 text-[10px] font-black text-slate-400 uppercase tracking-widest text-left w-12">
                      Day
                    </th>
                    <th className="py-3 px-2 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center bg-surface-container-lowest/30">
                      Temp (°C)
                    </th>
                    <th className="py-3 px-2 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center bg-surface-container-lowest/30">
                      Hum (%)
                    </th>
                    <th className="py-3 px-2 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center bg-surface-container-lowest/30 border-r border-white/5">
                      THI
                    </th>
                    <th className="py-3 px-2 text-[10px] font-black text-primary uppercase tracking-widest text-center">
                      Milk (L)
                    </th>
                    <th className="py-3 px-2 text-[10px] font-black text-primary uppercase tracking-widest text-center">
                      Water (L)
                    </th>
                    <th className="py-3 px-2 text-[10px] font-black text-primary uppercase tracking-widest text-center">
                      Feed (Kg)
                    </th>
                    <th className="py-3 px-2 text-[10px] font-black text-primary uppercase tracking-widest text-center">
                      Body T (°C)
                    </th>
                    <th className="py-3 px-2 text-[10px] font-black text-primary uppercase tracking-widest text-center">
                      Wt (Kg)
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {Array(7).fill(null).map((_, idx) => {
                    const weather = weatherData[idx] || { temp: 31.4, humidity: 78, thi: 82.4 }
                    return (
                      <tr key={idx} className="hover:bg-white/5 transition-colors">
                        <td className="py-3 px-2 text-xs font-bold text-white font-mono">
                          D{idx + 1}
                        </td>
                        <td className="py-3 px-2 text-center text-xs font-bold text-slate-300 bg-surface-container-lowest/30 font-mono">
                          {weather.temp.toFixed(1)}
                        </td>
                        <td className="py-3 px-2 text-center text-xs font-bold text-slate-300 bg-surface-container-lowest/30 font-mono">
                          {weather.humidity}%
                        </td>
                        <td className="py-3 px-2 text-center text-xs font-black bg-surface-container-lowest/30 font-mono border-r border-white/5">
                          <span className={weather.thi > 80 ? 'text-error' : 'text-slate-400'}>
                            {weather.thi.toFixed(1)}
                          </span>
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full bg-[#060e20] border-none rounded py-2 text-center text-xs font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1 min-w-[50px]"
                            type="number"
                            value={logsData.yields[idx]}
                            onChange={(e) => handleLogChange('yields', idx, e.target.value)}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full bg-[#060e20] border-none rounded py-2 text-center text-xs font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1 min-w-[50px]"
                            type="number"
                            value={logsData.water[idx]}
                            onChange={(e) => handleLogChange('water', idx, e.target.value)}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full bg-[#060e20] border-none rounded py-2 text-center text-xs font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1 min-w-[50px]"
                            type="number"
                            value={logsData.feed[idx]}
                            onChange={(e) => handleLogChange('feed', idx, e.target.value)}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full bg-[#060e20] border-none rounded py-2 text-center text-xs font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1 min-w-[50px]"
                            type="number"
                            value={logsData.temp[idx]}
                            onChange={(e) => handleLogChange('temp', idx, e.target.value)}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            className="w-full bg-[#060e20] border-none rounded py-2 text-center text-xs font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1 min-w-[50px]"
                            type="number"
                            value={logsData.weight[idx]}
                            onChange={(e) => handleLogChange('weight', idx, e.target.value)}
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* GPS / Environmental Status Bar */}
      <div className="w-full">
        <div className="bg-[#171f33] rounded-xl p-5 border-l-4 border-secondary flex flex-col md:flex-row items-center justify-between gap-6 relative overflow-hidden">
          <div className="flex items-center gap-4 relative z-10">
            <div className="w-10 h-10 rounded-full bg-secondary/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-secondary animate-pulse">radar</span>
            </div>
            <div>
              <h4 className="text-[10px] font-black text-secondary tracking-widest uppercase">
                Live GPS Synced
              </h4>
              <p className="text-on-surface text-sm font-medium">
                {weatherFetched 
                  ? `Successfully synced with ${activeLocation || 'Kandy'} Station` 
                  : 'Ready to Fetch Local Weather Station Logs'}
              </p>
            </div>
          </div>
          <div className="flex gap-8 relative z-10">
            <div className="text-center">
              <p className="text-[9px] font-black text-slate-400 uppercase">Avg Ambient Temp</p>
              <p className="text-lg font-bold text-on-surface">
                {(weatherData.reduce((sum, w) => sum + w.temp, 0) / 7).toFixed(1)}°C
              </p>
            </div>
            <div className="text-center">
              <p className="text-[9px] font-black text-slate-400 uppercase">Avg Humidity</p>
              <p className="text-lg font-bold text-on-surface">
                {(weatherData.reduce((sum, w) => sum + w.humidity, 0) / 7).toFixed(0)}%
              </p>
            </div>
            <div className="text-center">
              <p className="text-[9px] font-black text-secondary uppercase">Avg THI</p>
              <p className="text-lg font-black text-secondary">
                {(weatherData.reduce((sum, w) => sum + w.thi, 0) / 7).toFixed(1)}
                {weatherFetched && (weatherData.reduce((sum, w) => sum + w.thi, 0) / 7) > 80 && (
                  <span className="text-[9px] font-normal text-error ml-1">[STRESS]</span>
                )}
              </p>
            </div>
          </div>
          <div className="absolute right-0 top-0 h-full w-48 opacity-10">
            <img
              alt="Map background"
              className="h-full w-full object-cover"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuC5dvK_WKT77odUdmwrY5QnXxX8YKiB9-IAuUM3xR3KRGN0UHrEFXA0DNCT8G6LJxNXxIv-GUfmReDRVuyoYjDUlW12BSjSESkic-aQ9K1giY3O_KRwRYmw8u7cqAh_Lh6bfkkvepFac5xxjZvsQbrSGjywfRbL-puE_hzEx_cBypeLJTYvH9cSQL545nKpzmGLFCtnxbizlFpYESu68aI5JCUvWK1k3_xgVzKjwg6Y6cxfc3dL1S-mfgFXmNTbY9zyhSgiObXXJcR8"
            />
          </div>
        </div>
      </div>

      {/* Action Button */}
      <div className="pt-4">
        <button
          onClick={handleRunDiagnostics}
          className="group relative overflow-hidden bg-primary rounded-xl p-6 w-full flex items-center justify-center text-on-primary transition-all duration-300 hover:scale-[1.01] hover:shadow-2xl hover:shadow-primary/20"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="flex items-center gap-4 relative z-10">
            <span
              className="material-symbols-outlined text-3xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              bolt
            </span>
            <span className="text-xl font-bold uppercase tracking-widest">
              Run Multi-Modal AI Diagnostics
            </span>
            <span className="material-symbols-outlined text-3xl group-hover:translate-x-2 transition-transform">
              arrow_forward
            </span>
          </div>
        </button>
      </div>

      {/* Weather Source Selection Modal */}
      {isWeatherModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="bg-[#111827] border border-white/10 rounded-2xl p-6 max-w-sm w-full shadow-2xl relative space-y-6 text-center">
            <div className="space-y-2">
              <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center text-primary mx-auto ring-4 ring-primary/5">
                <span className="material-symbols-outlined text-2xl animate-pulse">cloud</span>
              </div>
              <h3 className="text-lg font-bold text-white uppercase tracking-tight">Select Weather Source</h3>
              <p className="text-xs text-slate-400">
                Choose how the AI Triage system retrieves 7-Day physiological ambient records.
              </p>
            </div>

            {gpsLoading ? (
              <div className="py-6 space-y-4">
                <div className="w-12 h-12 rounded-full border-4 border-primary/20 border-t-primary animate-spin mx-auto"></div>
                <p className="text-xs text-primary font-bold uppercase tracking-widest animate-pulse">
                  Querying GPS Coordinates...
                </p>
              </div>
            ) : gpsResult ? (
              <div className="py-4 space-y-3 bg-primary/5 border border-primary/15 rounded-xl p-4 animate-scaleUp">
                <span className="material-symbols-outlined text-3xl text-primary animate-bounce">location_on</span>
                <div className="space-y-1">
                  <p className="text-xs font-bold text-white uppercase tracking-wide">Coordinates Acquired</p>
                  <p className="text-[10px] text-slate-400 font-mono">Lat: {gpsResult.lat} | Lon: {gpsResult.lon}</p>
                  <p className="text-xs font-black text-primary uppercase mt-1">District: {gpsResult.district}</p>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <button
                  onClick={handleFetchOptionA}
                  className="w-full py-3.5 bg-primary hover:opacity-90 text-on-primary font-bold text-xs uppercase tracking-wider rounded-lg transition-all flex items-center justify-center gap-2"
                >
                  <span className="material-symbols-outlined text-sm">my_location</span>
                  Use Current Device GPS
                </button>
                
                <button
                  onClick={handleFetchOptionB}
                  className="w-full py-3.5 bg-surface-container-highest hover:bg-surface-bright text-white font-bold text-xs uppercase tracking-wider rounded-lg transition-all flex items-center justify-center gap-2 border border-white/5"
                >
                  <span className="material-symbols-outlined text-sm">agriculture</span>
                  Use Registered Farm Location
                </button>
              </div>
            )}

            <div className="pt-2 border-t border-white/5">
              <button
                onClick={() => setIsWeatherModalOpen(false)}
                className="text-xs text-slate-500 hover:text-white uppercase tracking-widest font-bold bg-transparent border-none cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
