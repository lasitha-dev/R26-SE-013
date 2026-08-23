import React from 'react'

export default function GeospatialMock() {
  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-white/5">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-mono font-bold uppercase tracking-wider">
              Epidemiological Surveillance
            </span>
            <span className="text-slate-600 text-xs">•</span>
            <span className="text-slate-400 text-xs font-mono">Geo-Spatial GIS Layer</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
            Geospatial Intelligence
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Real-time localized outbreak velocities, spatial disease clustering, and regional vector mapping.
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
      <div className="rounded-2xl p-8 md:p-12 flex flex-col items-center justify-center min-h-[460px] bg-gradient-to-b from-surface-container-high via-surface-container to-surface-container-low border border-emerald-500/20 relative overflow-hidden shadow-2xl">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(78,222,163,0.08),transparent_65%)] pointer-events-none" />
        
        {/* Animated Map Grid lines */}
        <div className="absolute inset-0 opacity-10 bg-[linear-gradient(to_right,#10b981_1px,transparent_1px),linear-gradient(to_bottom,#10b981_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

        <div className="relative z-10 flex flex-col items-center text-center max-w-xl">
          <div className="w-20 h-20 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-6 shadow-glow-sm">
            <span className="material-symbols-outlined text-4xl text-emerald-400 animate-pulse">
              travel_explore
            </span>
          </div>
          
          <h3 className="text-xl font-bold text-white mb-2 tracking-tight">
            Interactive Geospatial Heatmap &amp; Cluster Tracking
          </h3>
          
          <p className="text-sm text-slate-400 leading-relaxed mb-6">
            The Geospatial Intelligence module correlates clinical diagnoses across registered regional herds to detect infectious disease clusters, path-of-travel contagion risk, and spatial transmission vectors.
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
                Active Hotspots
              </span>
              <span className="text-sm font-bold text-white">0 Identified</span>
              <p className="text-[10px] text-slate-500 mt-0.5">In regional grid</p>
            </div>
            <div className="p-3.5 rounded-xl bg-surface-container-lowest/80 border border-outline-variant/10 text-left">
              <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-widest block mb-1">
                Spatial Index
              </span>
              <span className="text-sm font-bold text-white">2dsphere Query</span>
              <p className="text-[10px] text-slate-500 mt-0.5">MongoDB geospatial</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
