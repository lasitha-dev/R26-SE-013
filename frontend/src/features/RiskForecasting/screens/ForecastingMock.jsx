import React from 'react'

export default function ForecastingMock() {
  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-white/5">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-mono font-bold uppercase tracking-wider">
              Predictive Epidemiology
            </span>
            <span className="text-slate-600 text-xs">•</span>
            <span className="text-slate-400 text-xs font-mono">Climate Correlation Engine</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
            Seasonal Risk Forecasting
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Time-series forecasting models integrated with meteorological trends, monsoon shifts, and historical pathogen cycles.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#131b2e] border border-emerald-500/20 text-emerald-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span>FORECAST MODEL READY</span>
          </div>
        </div>
      </div>

      {/* Main Visual Display */}
      <div className="rounded-2xl p-8 md:p-12 flex flex-col items-center justify-center min-h-[460px] bg-gradient-to-b from-surface-container-high via-surface-container to-surface-container-low border border-emerald-500/20 relative overflow-hidden shadow-2xl">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(78,222,163,0.08),transparent_65%)] pointer-events-none" />
        
        {/* Subtle decorative elements */}
        <div className="relative z-10 flex flex-col items-center text-center max-w-xl">
          <div className="w-20 h-20 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-6 shadow-glow-sm">
            <span className="material-symbols-outlined text-4xl text-emerald-400 animate-pulse">
              wb_sunny
            </span>
          </div>
          
          <h3 className="text-xl font-bold text-white mb-2 tracking-tight">
            Predictive Climate-Disease Risk Index
          </h3>
          
          <p className="text-sm text-slate-400 leading-relaxed mb-6">
            Correlates high-resolution weather datasets, humidity anomalies, and temperature trends to forecast seasonal vulnerability windows for tick-borne diseases, respiratory infections, and mastitis.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full">
            <div className="p-3.5 rounded-xl bg-surface-container-lowest/80 border border-outline-variant/10 text-left">
              <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-widest block mb-1">
                Seasonal Window
              </span>
              <span className="text-sm font-bold text-white">Q3 Monsoonal</span>
              <p className="text-[10px] text-slate-500 mt-0.5">High humidity period</p>
            </div>
            <div className="p-3.5 rounded-xl bg-surface-container-lowest/80 border border-outline-variant/10 text-left">
              <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-widest block mb-1">
                Risk Index
              </span>
              <span className="text-sm font-bold text-amber-400">Moderate (0.42)</span>
              <p className="text-[10px] text-slate-500 mt-0.5">Bovine Respiratory Index</p>
            </div>
            <div className="p-3.5 rounded-xl bg-surface-container-lowest/80 border border-outline-variant/10 text-left">
              <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-widest block mb-1">
                Forecast Horizon
              </span>
              <span className="text-sm font-bold text-white">30-Day Outlook</span>
              <p className="text-[10px] text-slate-500 mt-0.5">Rolling probability</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
