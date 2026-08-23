import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function WellnessDashboard() {
  const [cattleData, setCattleData] = useState([])
  const [loadingCattle, setLoadingCattle] = useState(true)

  const [weatherData, setWeatherData] = useState({
    temp: 31.2,
    humidity: 62,
    thi: 74,
    stressLevel: 'Moderate Stress',
    stressColorClass: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
  })
  const [loadingWeather, setLoadingWeather] = useState(true)

  // 1. Fetch real cattle data from FastAPI backend
  useEffect(() => {
    const fetchCattle = async () => {
      try {
        setLoadingCattle(true)
        const token = localStorage.getItem('token')
        const response = await fetch('http://127.0.0.1:8000/api/cattle', {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        if (response.ok) {
          const data = await response.json()
          setCattleData(Array.isArray(data) ? data : [])
        }
      } catch (err) {
        console.error('Failed to fetch cattle data:', err)
      } finally {
        setLoadingCattle(false)
      }
    }
    fetchCattle()
  }, [])

  // 2. Fetch real-time weather data from Open-Meteo API & Calculate THI score
  useEffect(() => {
    const fetchWeather = async () => {
      try {
        setLoadingWeather(true)
        const lat = localStorage.getItem('registered_farm_lat') || 7.8731
        const lon = localStorage.getItem('registered_farm_lon') || 80.7718

        const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&hourly=relative_humidity_2m&timezone=auto`
        const res = await fetch(url)
        if (res.ok) {
          const data = await res.json()
          const temp = data.current_weather?.temperature ?? 30.0
          
          let humidity = 60
          if (data.hourly && data.hourly.time && data.hourly.relative_humidity_2m) {
            const currentTime = data.current_weather?.time
            const timeIdx = data.hourly.time.indexOf(currentTime)
            if (timeIdx !== -1) {
              humidity = data.hourly.relative_humidity_2m[timeIdx]
            } else if (data.hourly.relative_humidity_2m.length > 0) {
              humidity = data.hourly.relative_humidity_2m[0]
            }
          }

          // THI Calculation Formula: THI = (1.8 * T + 32) - (0.55 - 0.0055 * RH) * (1.8 * T - 26)
          const thiRaw = (1.8 * temp + 32) - (0.55 - 0.0055 * humidity) * (1.8 * temp - 26)
          const thi = Math.round(thiRaw)

          let stressLevel = 'Normal'
          let stressColorClass = 'bg-primary/20 text-primary border border-primary/30'

          if (thi >= 89) {
            stressLevel = 'Emergency Stress'
            stressColorClass = 'bg-error/30 text-error font-extrabold animate-pulse border border-error/50'
          } else if (thi >= 79) {
            stressLevel = 'Severe Stress'
            stressColorClass = 'bg-error-container text-on-error-container border border-error-container'
          } else if (thi >= 72) {
            stressLevel = 'Moderate Stress'
            stressColorClass = 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
          }

          setWeatherData({
            temp,
            humidity,
            thi,
            stressLevel,
            stressColorClass
          })
        }
      } catch (err) {
        console.error('Failed to fetch weather data:', err)
      } finally {
        setLoadingWeather(false)
      }
    }
    fetchWeather()
  }, [])

  // Dynamic Herd Statistics
  const totalCattle = cattleData.length
  const healthyCount = cattleData.filter(
    c => c.status === 'Healthy' || c.health_status === 'Healthy'
  ).length
  const atRiskCount = Math.max(0, totalCattle - healthyCount)

  // Dynamic BCS Assessments Table Data
  const bcsCattle = cattleData
    .filter(c => c.bcs_score !== null && c.bcs_score !== undefined && !isNaN(Number(c.bcs_score)))
    .sort((a, b) => new Date(b.last_scored_date || b.last_updated || 0) - new Date(a.last_scored_date || a.last_updated || 0))
    .slice(0, 4)

  // THI Gauge Circumference Calculation (r = 58 -> C = 364.4)
  const thiCircleOffset = 364.4 * (1 - Math.min(weatherData.thi, 100) / 100)

  // Helper for BCS Condition Styling
  const getBcsCondition = (score) => {
    const num = Number(score)
    if (num < 2.5) {
      return {
        label: 'Under-conditioned',
        badgeClass: 'bg-error/10 text-error border border-error/20',
        textClass: 'text-error'
      }
    } else if (num <= 3.75) {
      return {
        label: 'Optimal',
        badgeClass: 'bg-primary/10 text-primary border border-primary/20',
        textClass: 'text-primary'
      }
    } else {
      return {
        label: 'Over-conditioned',
        badgeClass: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
        textClass: 'text-yellow-400'
      }
    }
  }

  return (
    <div className="space-y-8">
      {/* Page Title & Intro */}
      <div className="flex flex-col gap-1">
        <h2 className="text-3xl font-extrabold tracking-tight text-on-surface">
          Herd Wellness Dashboard
        </h2>
        <p className="text-slate-400">
          Real-time biosecurity surveillance and Body Condition Scoring (BCS) analytics.
        </p>
      </div>

      {/* Overview Cards & THI Meter */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Environmental Stress Card */}
        <div className="col-span-12 lg:col-span-5 glass-card rounded-xl p-6 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute -right-12 -top-12 w-48 h-48 bg-primary/10 rounded-full blur-3xl"></div>
          <div className="flex justify-between items-start mb-6">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.1em] text-slate-500 mb-1">
                Environmental Stress
              </p>
              <h3 className="text-xl font-bold">Temperature-Humidity Index</h3>
            </div>
            <div className={`px-3 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${weatherData.stressColorClass}`}>
              {loadingWeather ? 'Calculating...' : weatherData.stressLevel}
            </div>
          </div>

          <div className="flex items-end gap-6 mb-4">
            <div className="flex-shrink-0 relative">
              <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 128 128">
                <circle
                  className="text-surface-container-highest"
                  cx="64"
                  cy="64"
                  fill="transparent"
                  r="58"
                  stroke="currentColor"
                  strokeWidth="8"
                />
                <circle
                  className="text-primary transition-all duration-1000 ease-out"
                  cx="64"
                  cy="64"
                  fill="transparent"
                  r="58"
                  stroke="currentColor"
                  strokeDasharray="364.4"
                  strokeDashoffset={loadingWeather ? 364.4 : thiCircleOffset}
                  strokeWidth="8"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-black text-on-surface">
                  {loadingWeather ? '--' : weatherData.thi}
                </span>
                <span className="text-[10px] uppercase text-slate-400">THI Score</span>
              </div>
            </div>

            <div className="flex-1 space-y-4">
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-medium">
                  <span className="text-slate-400">Ambient Temp</span>
                  <span className="text-on-surface">
                    {loadingWeather ? '-- °C' : `${weatherData.temp.toFixed(1)}°C`}
                  </span>
                </div>
                <div className="w-full h-1 bg-surface-container-highest rounded-full overflow-hidden">
                  <div
                    className="bg-primary h-full transition-all duration-700"
                    style={{ width: `${Math.min((weatherData.temp / 50) * 100, 100)}%` }}
                  ></div>
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-medium">
                  <span className="text-slate-400">Rel. Humidity</span>
                  <span className="text-on-surface">
                    {loadingWeather ? '-- %' : `${Math.round(weatherData.humidity)}%`}
                  </span>
                </div>
                <div className="w-full h-1 bg-surface-container-highest rounded-full overflow-hidden">
                  <div
                    className="bg-primary h-full transition-all duration-700"
                    style={{ width: `${Math.min(weatherData.humidity, 100)}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Overview Stats Column */}
        <div className="col-span-12 lg:col-span-7 grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Total Registered Cattle */}
          <div className="bg-surface-container rounded-xl p-6 flex flex-col justify-between border border-white/5">
            <div className="flex items-center justify-between">
              <span className="material-symbols-outlined text-primary text-2xl">groups</span>
              <span className="material-symbols-outlined text-primary text-sm">trending_up</span>
            </div>
            <div>
              <p className="text-3xl font-black text-on-surface mt-4">
                {loadingCattle ? '...' : totalCattle.toLocaleString()}
              </p>
              <p className="text-xs uppercase font-bold tracking-widest text-slate-500 mt-1">
                Registered Cattle
              </p>
            </div>
          </div>

          {/* Healthy Count */}
          <div className="bg-surface-container rounded-xl p-6 flex flex-col justify-between border border-white/5">
            <div className="flex items-center justify-between">
              <span
                className="material-symbols-outlined text-primary text-2xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="material-symbols-outlined text-primary text-sm">trending_up</span>
            </div>
            <div>
              <p className="text-3xl font-black text-on-surface mt-4">
                {loadingCattle ? '...' : healthyCount.toLocaleString()}
              </p>
              <p className="text-xs uppercase font-bold tracking-widest text-slate-500 mt-1">
                Healthy
              </p>
            </div>
          </div>

          {/* At Risk Count */}
          <div className="bg-surface-container rounded-xl p-6 flex flex-col justify-between border border-white/5">
            <div className="flex items-center justify-between">
              <span className="material-symbols-outlined text-error text-2xl">warning</span>
              <span className="material-symbols-outlined text-error text-sm">
                {atRiskCount > 0 ? 'trending_down' : 'remove'}
              </span>
            </div>
            <div>
              <p className="text-3xl font-black text-on-surface mt-4">
                {loadingCattle ? '...' : atRiskCount.toLocaleString()}
              </p>
              <p className="text-xs uppercase font-bold tracking-widest text-slate-500 mt-1">
                At Risk
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Actions (Links to intake and scan) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <Link
          to="/health/wellness-data-intake"
          className="group relative overflow-hidden bg-surface-container-high rounded-xl p-8 flex flex-col text-left transition-all duration-300 hover:scale-[1.01] hover:shadow-2xl hover:shadow-primary/10"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="mb-6 w-14 h-14 bg-primary-container rounded-lg flex items-center justify-center text-on-primary-container shadow-lg">
            <span className="material-symbols-outlined text-3xl">edit_note</span>
          </div>
          <h4 className="text-2xl font-bold text-on-surface mb-2">Log Daily Metrics</h4>
          <p className="text-slate-400 mb-8 max-w-sm">
            Manually input milk yield, hydration levels, and weight updates for targeted wellness monitoring.
          </p>
          <div className="mt-auto flex items-center gap-2 text-primary font-bold group-hover:gap-4 transition-all">
            <span>Initialize Input</span>
            <span className="material-symbols-outlined">arrow_forward</span>
          </div>
        </Link>

        <Link
          to="/health/7-day-triage-scan"
          className="group relative overflow-hidden bg-surface-container-high rounded-xl p-8 flex flex-col text-left transition-all duration-300 hover:scale-[1.01] hover:shadow-2xl hover:shadow-primary/10"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="mb-6 w-14 h-14 bg-primary rounded-lg flex items-center justify-center text-on-primary shadow-[0_0_20px_rgba(78,222,163,0.3)]">
            <span
              className="material-symbols-outlined text-3xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              radar
            </span>
          </div>
          <h4 className="text-2xl font-bold text-on-surface mb-2">Start 7-Day Triage Scan</h4>
          <p className="text-slate-400 mb-8 max-w-sm">
            Trigger the AI-powered geospatial and visual analysis engine for proactive disease identification across the herd.
          </p>
          <div className="mt-auto flex items-center gap-2 text-primary font-bold group-hover:gap-4 transition-all">
            <span>Launch Diagnosis</span>
            <span className="material-symbols-outlined">sensors</span>
          </div>
        </Link>

        <Link
          to="/health/bcs-analyzer"
          className="group relative overflow-hidden bg-surface-container-high rounded-xl p-8 flex flex-col text-left transition-all duration-300 hover:scale-[1.01] hover:shadow-2xl hover:shadow-primary/10"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="mb-6 w-14 h-14 bg-primary/20 rounded-lg flex items-center justify-center text-primary shadow-[0_0_20px_rgba(78,222,163,0.15)] border border-primary/20">
            <span className="material-symbols-outlined text-3xl">photo_camera</span>
          </div>
          <h4 className="text-2xl font-bold text-on-surface mb-2">Standalone BCS Analyzer</h4>
          <p className="text-slate-400 mb-8 max-w-sm">
            Leverage YOLOv8 vision and Keras CNN regression to automatically calculate localized Body Condition Scoring.
          </p>
          <div className="mt-auto flex items-center gap-2 text-primary font-bold group-hover:gap-4 transition-all">
            <span>Analyze Anatomy</span>
            <span className="material-symbols-outlined">center_focus_strong</span>
          </div>
        </Link>
      </div>

      {/* Assessments List & AI Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8 bg-surface-container rounded-xl overflow-hidden border border-white/5">
          <div className="p-6 border-b border-white/5 flex justify-between items-center">
            <h3 className="text-lg font-bold">Recent BCS Assessments</h3>
            <Link to="/health/herd-registry" className="text-primary text-xs font-bold uppercase tracking-widest hover:underline">
              View History
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-surface-container-low/50 text-[10px] uppercase font-bold tracking-widest text-slate-500">
                <tr>
                  <th className="px-6 py-4">ID Reference</th>
                  <th className="px-6 py-4">Current Score</th>
                  <th className="px-6 py-4">Last Scored Date</th>
                  <th className="px-6 py-4">AI Assessment Badge</th>
                  <th className="px-6 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {loadingCattle ? (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center text-slate-400 text-sm animate-pulse">
                      Loading herd assessments...
                    </td>
                  </tr>
                ) : bcsCattle.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center text-slate-500 text-sm">
                      No scored cattle assessments found.
                    </td>
                  </tr>
                ) : (
                  bcsCattle.map((c) => {
                    const cond = getBcsCondition(c.bcs_score)
                    return (
                      <tr key={c.id || c.identifier} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-6 py-4 font-mono text-xs text-on-surface font-semibold">
                          #{c.identifier}
                        </td>
                        <td className="px-6 py-4 font-bold">
                          {Number(c.bcs_score).toFixed(1)} / 5.0
                        </td>
                        <td className="px-6 py-4 text-slate-400 text-xs font-medium">
                          {c.last_scored_date || c.last_updated || 'Recent'}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${cond.badgeClass}`}>
                            {cond.label}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <Link
                            to={`/health/animal-profile-${c.id || c.identifier}`}
                            className="material-symbols-outlined text-slate-400 hover:text-primary transition-colors"
                          >
                            more_horiz
                          </Link>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 space-y-6">
          <div className="bg-surface-container rounded-xl p-6 border border-white/5">
            <div className="flex items-center gap-3 mb-6">
              <span className="material-symbols-outlined text-secondary">psychology</span>
              <h3 className="text-sm font-bold uppercase tracking-widest">AI Insights</h3>
            </div>
            <div className="space-y-4">
              <div className="p-3 bg-surface-container-low rounded-lg border-l-4 border-primary">
                <p className="text-xs font-medium text-on-surface">
                  Predicted yield increase of 4.2% if hydration monitoring remains consistent.
                </p>
              </div>
              <div className="p-3 bg-surface-container-low rounded-lg border-l-4 border-tertiary">
                <p className="text-xs font-medium text-on-surface">
                  Thermal imaging identifies cluster in Pen 4 with elevated surface temp.
                </p>
              </div>
            </div>
          </div>

          <div className="relative rounded-xl overflow-hidden group">
            <img
              alt="Livestock monitoring overview"
              className="w-full h-40 object-cover opacity-60 group-hover:scale-105 transition-transform duration-500"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuB1x8hsQpL-K87qXFsLtsh0cZO3PA6OMB53E8v8mXKk0zDxzOb6iM7DeSh1jaMekze8tiXqlBaM-A3WaWc_SM2vgFa_d9p0hl1eR-u4yC5zowQqioJU0dquYO1Yc81nlvZxW8FSQtZ2Se_cY-WUAd8ef0mqj5CFxv4RrMZ5OWD5Jv3WV0B9NP2pwi0q4jFTbhIJaYuFIrmhmvKzUTBTQRpIDZontFqIUexORLlhl_9qZPFqVBfhYHWyLoLfAkkS3ZFnrXHxUKT9rL9y"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-surface to-transparent flex flex-col justify-end p-4">
              <p className="text-xs font-bold text-white mb-1">Live Feed: North Sector</p>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse"></div>
                <span className="text-[10px] text-primary uppercase font-black">Encrypted Signal</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
