import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'

export default function SevenDayTriageScan() {
  const navigate = useNavigate()
  const location = useLocation()

  const [cattleList, setCattleList] = useState([])
  const [imageFile, setImageFile] = useState(null)
  const get7DayDates = (endDateStr) => {
    if (!endDateStr) return []
    const parts = endDateStr.split('-').map(Number)
    if (parts.length !== 3 || parts.some(isNaN)) return []
    const [year, month, day] = parts
    const baseDate = new Date(year, month - 1, day)
    const dates = []
    for (let i = 6; i >= 0; i--) {
      const d = new Date(baseDate)
      d.setDate(baseDate.getDate() - i)
      const yyyy = d.getFullYear()
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      dates.push(`${yyyy}-${mm}-${dd}`)
    }
    return dates
  }

  const normalizeDateStr = (raw) => {
    if (!raw) return ''
    const str = String(raw).trim()
    if (/^\d{4}-\d{2}-\d{2}$/.test(str)) return str

    const parts = str.split(/[\/\-]/)
    if (parts.length === 3) {
      const p1 = parseInt(parts[0], 10)
      const p2 = parseInt(parts[1], 10)
      const p3 = parseInt(parts[2], 10)
      if (!isNaN(p1) && !isNaN(p2) && !isNaN(p3)) {
        if (p1 > 1000) {
          return `${p1}-${String(p2).padStart(2, '0')}-${String(p3).padStart(2, '0')}`
        }
        let year = p3
        if (year < 100) year += 2000
        return `${year}-${String(p1).padStart(2, '0')}-${String(p2).padStart(2, '0')}`
      }
    }
    return str
  }

  const [selectedCattleId, setSelectedCattleId] = useState('')
  const [currentDate, setCurrentDate] = useState(new Date().toISOString().split('T')[0])
  const [weatherFetched, setWeatherFetched] = useState(false)
  const [weatherData, setWeatherData] = useState(
    Array(7).fill(null).map(() => ({ temp: 31.4, humidity: 78, thi: 82.4 }))
  )
  const [lockedRows, setLockedRows] = useState(Array(7).fill(false))
  const [validationError, setValidationError] = useState('')
  const [logsData, setLogsData] = useState({
    yields: [0, 0, 0, 0, 0, 0, 0],
    water: [48, 48, 48, 48, 48, 48, 48],
    feed: [14.0, 14.0, 14.0, 14.0, 14.0, 14.0, 14.0],
    temp: [38.5, 38.5, 38.5, 38.5, 38.5, 38.5, 38.5],
    weight: [0, 0, 0, 0, 0, 0, 0],
  })

  const [bcsPreview, setBcsPreview] = useState(null)
  const [bcsUploading, setBcsUploading] = useState(false)
  const [bcsScore, setBcsScore] = useState('')
  const [dragActive, setDragActive] = useState(false)

  // Auto-detect cattle_id and optional date from query params or route state
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const paramId = params.get('cattle_id') || location.state?.cattle_id
    if (paramId) {
      setSelectedCattleId(paramId)
    }
    const paramDate = params.get('date') || location.state?.date
    if (paramDate) {
      setCurrentDate(paramDate)
    }
  }, [location.search, location.state])

  // Target dates for the 7 slots (Day 1 = currentDate - 6 days, ..., Day 7 = currentDate)
  const targetDates = get7DayDates(currentDate)

  // Auto-populate 7-day logs from database when a cow or currentDate is selected
  useEffect(() => {
    if (!selectedCattleId) {
      setLockedRows(Array(7).fill(false))
      setLogsData({
        yields: [0, 0, 0, 0, 0, 0, 0],
        water: [48, 48, 48, 48, 48, 48, 48],
        feed: [14.0, 14.0, 14.0, 14.0, 14.0, 14.0, 14.0],
        temp: [38.5, 38.5, 38.5, 38.5, 38.5, 38.5, 38.5],
        weight: [0, 0, 0, 0, 0, 0, 0],
      })
      return
    }

    const fetchCattleLogs = async () => {
      try {
        const token = localStorage.getItem('token')
        const headers = { Authorization: token ? `Bearer ${token}` : '' }
        const res = await fetch(`http://127.0.0.1:8000/api/cattle/${selectedCattleId}/daily-logs`, { headers })
        let logs = []
        if (res.ok) {
          const data = await res.json()
          if (Array.isArray(data)) logs = data
        }

        const dateMap = {}
        logs.forEach((l) => {
          const norm = normalizeDateStr(l.date)
          if (norm) {
            dateMap[norm] = l
          }
        })

        const days7Dates = get7DayDates(currentDate)
        const newYields = [0, 0, 0, 0, 0, 0, 0]
        const newWeight = [0, 0, 0, 0, 0, 0, 0]
        const newLocked = Array(7).fill(false)
        const newWater = [48, 48, 48, 48, 48, 48, 48]
        const newFeed = [14.0, 14.0, 14.0, 14.0, 14.0, 14.0, 14.0]
        const newTemp = [38.5, 38.5, 38.5, 38.5, 38.5, 38.5, 38.5]

        days7Dates.forEach((dateStr, idx) => {
          const matchedLog = dateMap[dateStr]
          if (matchedLog) {
            newYields[idx] = (matchedLog.milk_yield !== undefined && matchedLog.milk_yield !== null)
              ? parseFloat(matchedLog.milk_yield)
              : 0
            newWeight[idx] = (matchedLog.weight !== undefined && matchedLog.weight !== null)
              ? parseFloat(matchedLog.weight)
              : 0
            newLocked[idx] = true

            if (matchedLog.water_intake !== undefined && matchedLog.water_intake !== null && Number(matchedLog.water_intake) > 0) {
              newWater[idx] = parseFloat(matchedLog.water_intake)
            }
            if (matchedLog.feed_intake !== undefined && matchedLog.feed_intake !== null && Number(matchedLog.feed_intake) > 0) {
              newFeed[idx] = parseFloat(matchedLog.feed_intake)
            }
            if (matchedLog.body_temp !== undefined && matchedLog.body_temp !== null && Number(matchedLog.body_temp) > 0) {
              newTemp[idx] = parseFloat(matchedLog.body_temp)
            }
          } else {
            newYields[idx] = 0
            newWeight[idx] = 0
            newLocked[idx] = false
          }
        })

        setLockedRows(newLocked)
        setLogsData({
          yields: newYields,
          weight: newWeight,
          water: newWater,
          feed: newFeed,
          temp: newTemp
        })
      } catch (err) {
        console.error('Error fetching cattle daily logs for 7-day intake:', err)
      }
    }

    fetchCattleLogs()
  }, [selectedCattleId, currentDate])

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

    const hydrateLocation = async () => {
      const storedLat = localStorage.getItem('registered_farm_lat')
      const storedLon = localStorage.getItem('registered_farm_lon')
      if (!storedLat || !storedLon) {
        const token = localStorage.getItem('token')
        if (token) {
          try {
            const res = await fetch('http://127.0.0.1:8000/api/user/profile', {
              headers: { Authorization: `Bearer ${token}` }
            })
            if (res.ok) {
              const data = await res.json()
              if (data.latitude !== null && data.latitude !== undefined && data.longitude !== null && data.longitude !== undefined) {
                localStorage.setItem('registered_farm_lat', data.latitude)
                localStorage.setItem('registered_farm_lon', data.longitude)
              }
              if (data.location_district) {
                localStorage.setItem('registered_farm_district', data.location_district)
                localStorage.setItem('registered_farm_name', data.location_district)
              }
              if (data.location) {
                localStorage.setItem('registered_farm_location', data.location)
              }
            }
          } catch (e) {
            console.error('Failed to auto-hydrate farm location in SevenDayTriageScan:', e)
          }
        }
      }
    }

    fetchCattle()
    hydrateLocation()
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

  const handleFetchOptionB = async () => {
    let lat = parseFloat(localStorage.getItem('registered_farm_lat'))
    let lon = parseFloat(localStorage.getItem('registered_farm_lon'))
    let district = localStorage.getItem('registered_farm_district') || 'Unknown'

    if (isNaN(lat) || isNaN(lon)) {
      const token = localStorage.getItem('token')
      if (token) {
        try {
          const res = await fetch('http://127.0.0.1:8000/api/user/profile', {
            headers: { Authorization: `Bearer ${token}` }
          })
          if (res.ok) {
            const data = await res.json()
            if (data.latitude !== null && data.latitude !== undefined && data.longitude !== null && data.longitude !== undefined) {
              lat = parseFloat(data.latitude)
              lon = parseFloat(data.longitude)
              district = data.location_district || 'Unknown'
              localStorage.setItem('registered_farm_lat', lat)
              localStorage.setItem('registered_farm_lon', lon)
              localStorage.setItem('registered_farm_district', district)
              localStorage.setItem('registered_farm_name', district)
            }
          }
        } catch (e) {
          console.error('Error hydrating location in Option B:', e)
        }
      }
    }

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
    if (validationError) {
      setValidationError('')
    }
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
      setValidationError('Please select a Cattle ID before running diagnostics.')
      return
    }

    // Validation: Check if any row still has milk <= 0 or weight <= 0
    const missingDays = []
    for (let i = 0; i < 7; i++) {
      const m = Number(logsData.yields[i])
      const w = Number(logsData.weight[i])
      if (isNaN(m) || m <= 0 || isNaN(w) || w <= 0) {
        const dStr = targetDates[i] ? targetDates[i].slice(5) : `Day ${i + 1}`
        missingDays.push(`D${i + 1} (${dStr})`)
      }
    }

    if (missingDays.length > 0) {
      setValidationError(
        `Incomplete 7-Day Physiological Records: Missing milk yield or weight for ${missingDays.join(', ')}. Please fill in all missing (0) values before proceeding.`
      )
      return
    }

    if (!imageFile) {
      setValidationError('Please upload a top-down cattle image before running diagnostics.')
      return
    }

    setValidationError('')

    const activeCattleObj = cattleList.find(c => c.id === selectedCattleId)
    if (!activeCattleObj) {
      setValidationError('Selected cattle record could not be found.')
      return
    }

    const GROUP_A = ['Ayrshire', 'Brown_Swiss', 'Danish_Red', 'Fleckvieh', 'Guernsey', 'Holstein-Friesian', 'Illawarra_Shorthorn', 'Jersey', 'Milking_Shorthorn', 'Montbeliarde', 'Normande', 'Norwegian_Red', 'Red_Poll_Africa', 'Simmental'];
    const GROUP_B = ['Ankole', 'Boran', 'Butana', 'Deoni', 'Gangatiri', 'Gir', 'Hariana', 'Kankrej', 'Kenana', 'Krishna_Valley', 'NDama', 'Ongole', 'Rathi', 'Red_Sindhi', 'Sahiwal', 'Tharparkar', 'White_Fulani', 'Local'];
    const GROUP_C = ['Australian_Friesian_Sahiwal', 'Australian_Milking_Zebu', 'Exotic_Local_Cross', 'Girolando', 'Holstein_Zebu_Cross', 'Jersey_Zebu_Cross', 'Tipo_Carora', 'Zebu_Cross_Brazil'];

    let calculatedGeneticGroup = 'Unknown';
    let modelGeneticGroup = 'C'; // Fallback to Crossbreed

    if (activeCattleObj && GROUP_A.includes(activeCattleObj.breed)) {
        calculatedGeneticGroup = 'Exotic / Temperate';
        modelGeneticGroup = 'A';
    } else if (activeCattleObj && GROUP_B.includes(activeCattleObj.breed)) {
        calculatedGeneticGroup = 'Tropical Indigenous';
        modelGeneticGroup = 'B';
    } else if (activeCattleObj && GROUP_C.includes(activeCattleObj.breed)) {
        calculatedGeneticGroup = 'Tropical Crossbreeds';
        modelGeneticGroup = 'C';
    }

    // Convert image to base64 so it can be passed through navigation state
    setBcsUploading(true)
    try {
      const imageBase64 = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = reject
        reader.readAsDataURL(imageFile)
      })

      // Navigate immediately — AiWellnessReport will make the actual API calls
      navigate('/health/ai-wellness-report', {
        state: {
          imageBase64,
          cattleId: selectedCattleId,
          activeCattle: activeCattleObj,
          weatherData,
          logsData,
          currentDate,
          modelGeneticGroup,
          calculatedGeneticGroup
        }
      })
    } catch (err) {
      alert(`Error preparing image: ${err.message}`)
    } finally {
      setBcsUploading(false)
    }
  }

  let calculatedAge = 'N/A'
  let calculatedDim = 'N/A'
  let activeCattle = null
  let calculatedGeneticGroup = 'Unknown';
  let calculatedLactationStage = 'N/A';

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

      const GROUP_A = ['Ayrshire', 'Brown_Swiss', 'Danish_Red', 'Fleckvieh', 'Guernsey', 'Holstein-Friesian', 'Illawarra_Shorthorn', 'Jersey', 'Milking_Shorthorn', 'Montbeliarde', 'Normande', 'Norwegian_Red', 'Red_Poll_Africa', 'Simmental'];
      const GROUP_B = ['Ankole', 'Boran', 'Butana', 'Deoni', 'Gangatiri', 'Gir', 'Hariana', 'Kankrej', 'Kenana', 'Krishna_Valley', 'NDama', 'Ongole', 'Rathi', 'Red_Sindhi', 'Sahiwal', 'Tharparkar', 'White_Fulani', 'Local'];
      const GROUP_C = ['Australian_Friesian_Sahiwal', 'Australian_Milking_Zebu', 'Exotic_Local_Cross', 'Girolando', 'Holstein_Zebu_Cross', 'Jersey_Zebu_Cross', 'Tipo_Carora', 'Zebu_Cross_Brazil'];

      if (activeCattle && GROUP_A.includes(activeCattle.breed)) {
          calculatedGeneticGroup = 'Exotic / Temperate';
      } else if (activeCattle && GROUP_B.includes(activeCattle.breed)) {
          calculatedGeneticGroup = 'Tropical Indigenous';
      } else if (activeCattle && GROUP_C.includes(activeCattle.breed)) {
          calculatedGeneticGroup = 'Tropical Crossbreeds';
      } else {
          calculatedGeneticGroup = 'Unknown';
      }

      if (activeCattle.calving_date) {
        const curDateVal = new Date(currentDate);
        const calvingDateVal = new Date(activeCattle.calving_date);
        const dimDays = Math.max(0, Math.floor((curDateVal - calvingDateVal) / (1000 * 60 * 60 * 24)));
        if (dimDays <= 100) calculatedLactationStage = 'Early Lactation';
        else if (dimDays <= 200) calculatedLactationStage = 'Mid Lactation';
        else if (dimDays <= 305) calculatedLactationStage = 'Late Lactation';
        else calculatedLactationStage = 'Dry Period';
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
              {cattleList
                .filter((c) => (c.gender || '').toLowerCase() !== 'male')
                .map((c) => (
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
            max={new Date().toISOString().split('T')[0]}
            onChange={(e) => {
              setCurrentDate(e.target.value)
              if (validationError) setValidationError('')
            }}
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
              <p className="text-xs font-bold text-white mt-1 uppercase">{calculatedGeneticGroup}</p>
            </div>
            <div className="bg-[#060e20]/60 border border-white/5 rounded-xl p-3 text-center">
              <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Lactation Stage</p>
              <p className="text-xs font-bold text-white mt-1 uppercase">{calculatedLactationStage}</p>
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
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-secondary">clinical_notes</span>
                <div>
                  <h3 className="text-base font-bold text-on-surface tracking-tight uppercase">
                    7-Day Physiological Logs
                  </h3>
                  <p className="text-[10px] text-slate-400">
                    Recorded logs are locked. Missing days (0) must be entered manually before scan.
                  </p>
                </div>
              </div>
              {weatherFetched && (
                <span className="px-2 py-1 bg-secondary/15 text-[9px] font-black text-secondary border border-secondary/20 rounded uppercase tracking-wider animate-pulse">
                  Weather Synced
                </span>
              )}
            </div>

            {/* Validation Error Banner */}
            {validationError && (
              <div 
                data-testid="triage-validation-banner" 
                className="bg-error/15 border border-error/40 text-error px-4 py-3 rounded-xl flex items-center gap-3 animate-fadeIn mb-4"
              >
                <span className="material-symbols-outlined text-xl shrink-0">error</span>
                <p className="text-xs font-bold uppercase tracking-wide leading-relaxed">{validationError}</p>
              </div>
            )}

            <div className="flex-1 overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="py-3 px-2 text-[10px] font-black text-slate-400 uppercase tracking-widest text-left whitespace-nowrap">
                      Day (Date)
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
                  {targetDates.map((dateStr, idx) => {
                    const weather = weatherData[idx] || { temp: 31.4, humidity: 78, thi: 82.4 }
                    const isLocked = lockedRows[idx]
                    const shortDate = dateStr ? dateStr.slice(5) : `Day ${idx + 1}`
                    const hasMilkError = validationError && Number(logsData.yields[idx]) <= 0
                    const hasWeightError = validationError && Number(logsData.weight[idx]) <= 0

                    return (
                      <tr key={idx} className={`hover:bg-white/5 transition-colors ${isLocked ? 'bg-white/[0.02]' : ''}`}>
                        <td className="py-3 px-2 text-xs font-bold text-white font-mono whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span className={isLocked ? 'text-primary' : 'text-slate-300'}>D{idx + 1}</span>
                            <span className="text-[10px] text-slate-400 font-normal">({shortDate})</span>
                            {isLocked ? (
                              <span 
                                className="material-symbols-outlined text-[14px] text-primary" 
                                title="Auto-populated from Database (Locked)"
                              >
                                lock
                              </span>
                            ) : (
                              <span 
                                className="material-symbols-outlined text-[14px] text-amber-400/70" 
                                title="Manual Entry Required (No DB Log)"
                              >
                                edit
                              </span>
                            )}
                          </div>
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
                            disabled={isLocked}
                            className={`w-full rounded py-2 text-center text-xs font-bold transition-all px-1 min-w-[50px] ${
                              isLocked
                                ? 'bg-[#060e20]/40 border border-white/5 text-slate-400 opacity-60 cursor-not-allowed select-none'
                                : 'bg-[#060e20] border border-white/10 text-primary focus:ring-1 focus:ring-primary shadow-inner cursor-text'
                            } ${hasMilkError ? 'ring-1 ring-error border-error text-error' : ''}`}
                            type="number"
                            step="0.1"
                            value={logsData.yields[idx]}
                            onChange={(e) => handleLogChange('yields', idx, e.target.value)}
                            title={isLocked ? 'Locked from database log' : 'Enter milk yield'}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            disabled={false}
                            className="w-full bg-[#060e20] border border-white/10 rounded py-2 text-center text-xs font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1 min-w-[50px]"
                            type="number"
                            step="0.1"
                            value={logsData.water[idx]}
                            onChange={(e) => handleLogChange('water', idx, e.target.value)}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            disabled={false}
                            className="w-full bg-[#060e20] border border-white/10 rounded py-2 text-center text-xs font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1 min-w-[50px]"
                            type="number"
                            step="0.1"
                            value={logsData.feed[idx]}
                            onChange={(e) => handleLogChange('feed', idx, e.target.value)}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            disabled={false}
                            className="w-full bg-[#060e20] border border-white/10 rounded py-2 text-center text-xs font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1 min-w-[50px]"
                            type="number"
                            step="0.1"
                            value={logsData.temp[idx]}
                            onChange={(e) => handleLogChange('temp', idx, e.target.value)}
                          />
                        </td>
                        <td className="p-1">
                          <input
                            disabled={isLocked}
                            className={`w-full rounded py-2 text-center text-xs font-bold transition-all px-1 min-w-[50px] ${
                              isLocked
                                ? 'bg-[#060e20]/40 border border-white/5 text-slate-400 opacity-60 cursor-not-allowed select-none'
                                : 'bg-[#060e20] border border-white/10 text-primary focus:ring-1 focus:ring-primary shadow-inner cursor-text'
                            } ${hasWeightError ? 'ring-1 ring-error border-error text-error' : ''}`}
                            type="number"
                            step="0.1"
                            value={logsData.weight[idx]}
                            onChange={(e) => handleLogChange('weight', idx, e.target.value)}
                            title={isLocked ? 'Locked from database log' : 'Enter cattle weight'}
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

      {/* Validation Error Banner Above Run Button */}
      {validationError && (
        <div 
          data-testid="triage-validation-banner-action" 
          className="bg-error/15 border border-error/40 text-error px-4 py-3 rounded-xl flex items-center gap-3 animate-fadeIn"
        >
          <span className="material-symbols-outlined text-xl shrink-0">error</span>
          <p className="text-xs font-bold uppercase tracking-wide leading-relaxed">{validationError}</p>
        </div>
      )}

      {/* Action Button */}
      <div className="pt-2">
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
