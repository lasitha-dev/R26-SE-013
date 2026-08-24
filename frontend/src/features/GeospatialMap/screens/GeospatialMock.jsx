import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function GeospatialMock() {
  const [farms, setFarms] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchFarms = async () => {
      try {
        const token = localStorage.getItem('token')
        const response = await fetch('http://127.0.0.1:8000/api/vet/my-farms', {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        })
        if (response.ok) {
          const data = await response.json()
          setFarms(Array.isArray(data) ? data : [])
        }
      } catch (err) {
        console.error('Error fetching farms for GIS:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchFarms()
  }, [])

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-white/5">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-mono font-bold uppercase tracking-wider">
              Epidemiological Surveillance
            </span>
            <span className="text-slate-600 text-xs">•</span>
            <span className="text-slate-400 text-xs font-mono">Geo-Spatial GIS Layer</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
            Geospatial Intelligence
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Real-time localized outbreak velocities, spatial disease clustering, and regional farm GPS node mapping.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#131b2e] border border-emerald-500/20 text-emerald-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span>GIS NODE ONLINE</span>
          </div>
        </div>
      </div>

      {/* Main Visual Display */}
      <div className="rounded-2xl p-6 md:p-10 flex flex-col items-center justify-center min-h-[380px] bg-gradient-to-b from-surface-container-high via-surface-container to-surface-container-low border border-emerald-500/20 relative overflow-hidden shadow-2xl">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(78,222,163,0.08),transparent_65%)] pointer-events-none" />
        <div className="absolute inset-0 opacity-10 bg-[linear-gradient(to_right,#10b981_1px,transparent_1px),linear-gradient(to_bottom,#10b981_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

        <div className="relative z-10 flex flex-col items-center text-center max-w-xl">
          <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-4 shadow-glow-sm">
            <span className="material-symbols-outlined text-3xl text-emerald-400 animate-pulse">
              travel_explore
            </span>
          </div>
          
          <h3 className="text-lg md:text-xl font-bold text-white mb-2 tracking-tight">
            Interactive Geospatial Heatmap &amp; Cluster Tracking
          </h3>
          
          <p className="text-xs md:text-sm text-slate-400 leading-relaxed mb-6">
            The Geospatial Intelligence module correlates clinical diagnoses and farm owner GPS coordinates across registered regional herds to detect infectious disease clusters, path-of-travel contagion risk, and spatial transmission vectors.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full">
            <div className="p-3.5 rounded-xl bg-surface-container-lowest/80 border border-outline-variant/10 text-left">
              <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-widest block mb-1">
                Vector Radii
              </span>
              <span className="text-sm font-bold text-white">25 km Radius</span>
              <p className="text-[10px] text-slate-500 mt-0.5">Surveillance zone</p>
            </div>
            <div className="p-3.5 rounded-xl bg-surface-container-lowest/80 border border-outline-variant/10 text-left">
              <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-widest block mb-1">
                Linked GPS Nodes
              </span>
              <span className="text-sm font-bold text-white">{farms.length} Estates</span>
              <p className="text-[10px] text-slate-500 mt-0.5">In jurisdictional grid</p>
            </div>
            <div className="p-3.5 rounded-xl bg-surface-container-lowest/80 border border-outline-variant/10 text-left">
              <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-widest block mb-1">
                Spatial Index
              </span>
              <span className="text-sm font-bold text-white">2dsphere Coordinates</span>
              <p className="text-[10px] text-slate-500 mt-0.5">Real-time GPS telemetry</p>
            </div>
          </div>
        </div>
      </div>

      {/* Linked Farm GPS Nodes Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <span className="material-symbols-outlined text-emerald-400 text-base">pin_drop</span>
            Linked Farm GPS Nodes &amp; Jurisdictional Coordinates
          </h3>
          <span className="text-xs text-slate-400 font-mono">{farms.length} GPS endpoints configured</span>
        </div>

        {loading ? (
          <div className="p-8 text-center text-slate-400 text-xs animate-pulse">
            Loading farm GPS coordinates...
          </div>
        ) : farms.length === 0 ? (
          <div className="p-6 bg-surface-container-lowest/40 rounded-xl border border-dashed border-white/10 text-center text-xs text-slate-400">
            No farms linked yet. Once farm owners link your license and configure their GPS coordinates in settings, their geographic nodes will appear here.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {farms.map((farm) => (
              <div
                key={farm.id}
                className="glass-card rounded-xl p-5 border border-white/5 hover:border-emerald-500/30 transition-all space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-sm font-bold text-white">{farm.owner_name}&apos;s Estate</h4>
                    <p className="text-xs text-slate-400">{farm.location_district}</p>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {farm.registration_number}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-surface-container-lowest/70 border border-white/5 font-mono text-xs space-y-1">
                  <div className="flex items-center justify-between text-slate-400">
                    <span>GPS Coordinates:</span>
                    <span className="text-emerald-400 font-bold">
                      {farm.latitude && farm.longitude
                        ? `${farm.latitude.toFixed(4)}, ${farm.longitude.toFixed(4)}`
                        : 'Resolved via District'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-slate-400">
                    <span>Total Livestock:</span>
                    <span className="text-white font-bold">{farm.total_animals}</span>
                  </div>
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <Link
                    to={`/vet/farm/${farm.id}`}
                    className="text-xs font-bold text-emerald-400 hover:underline flex items-center gap-1"
                  >
                    <span>Inspect Herd</span>
                    <span className="material-symbols-outlined text-xs">arrow_forward</span>
                  </Link>
                  <Link
                    to={`/vet/diagnostics?farm_id=${farm.id}`}
                    className="text-xs font-bold text-primary hover:underline flex items-center gap-1"
                  >
                    <span>Run Diagnostic</span>
                    <span className="material-symbols-outlined text-xs">psychology</span>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

