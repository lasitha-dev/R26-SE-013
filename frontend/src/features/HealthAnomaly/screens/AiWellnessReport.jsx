import React from 'react'
import { Link } from 'react-router-dom'

export default function AiWellnessReport() {
  return (
    <div className="space-y-8">
      {/* Title & Back Button */}
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
        <div className="flex items-center gap-2 mt-2 mb-2">
          <span className="inline-block w-2 h-2 bg-primary rounded-full animate-pulse"></span>
          <span className="text-[10px] font-bold tracking-[0.2em] text-primary uppercase">
            Active Session: Animal ID-8842
          </span>
        </div>
        <h2 className="text-4xl font-extrabold tracking-tighter text-white mb-2 font-headline">
          DIAGNOSTIC TRIAGE RESULTS
        </h2>
        <div className="h-1 w-24 bg-gradient-to-r from-primary to-transparent rounded-full mt-1"></div>
      </header>

      {/* Grid: XAI & Score Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Grad-CAM XAI Output */}
        <section className="lg:col-span-7 bg-surface-container-low rounded-xl overflow-hidden p-1 shadow-2xl relative border border-white/5">
          <div className="absolute top-6 left-6 z-10 bg-surface-container-highest/60 backdrop-blur-md px-3 py-1.5 rounded-full flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-sm">visibility</span>
            <span className="text-[10px] font-bold tracking-wider text-white uppercase">
              XAI Feature Extraction map
            </span>
          </div>
          <div className="aspect-[16/10] bg-surface-container-lowest rounded-lg overflow-hidden flex items-center justify-center">
            <div className="w-full h-full bg-slate-800 relative flex items-center justify-center overflow-hidden">
              <div
                className="absolute inset-0 opacity-60"
                style={{
                  background:
                    'radial-gradient(circle at 30% 40%, rgba(239, 68, 68, 0.8) 0%, transparent 40%), radial-gradient(circle at 70% 60%, rgba(249, 115, 22, 0.7) 0%, transparent 50%), radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.4) 0%, transparent 70%)'
                }}
              ></div>
              <div
                className="absolute inset-0 opacity-10"
                style={{
                  backgroundImage:
                    'linear-gradient(#94a3b8 1px, transparent 1px), linear-gradient(90deg, #94a3b8 1px, transparent 1px)',
                  backgroundSize: '40px 40px'
                }}
              ></div>
              <div className="absolute inset-0 pointer-events-none opacity-20">
                <div className="absolute top-1/2 left-0 w-full h-[1px] bg-white"></div>
                <div className="absolute top-0 left-1/2 w-[1px] h-full bg-white"></div>
              </div>
              <div className="relative z-10 bg-slate-900/80 backdrop-blur-md border border-slate-700 px-6 py-4 rounded-lg shadow-2xl mx-4">
                <p className="text-xs md:text-sm font-mono text-white tracking-wider text-center">
                  [ Grad-CAM XAI Output: Insert YOLOv8 Inference Image Here ]
                </p>
              </div>
            </div>
            <div className="absolute inset-0 pointer-events-none mix-blend-screen bg-gradient-to-b from-transparent via-primary/5 to-transparent"></div>
          </div>
          <div className="p-4 flex justify-between items-center bg-surface-container-low">
            <p className="text-xs text-slate-400 font-medium">
              Grad-CAM Score: <span className="text-primary">0.942 Intensity</span>
            </p>
            <div className="flex gap-2">
              <span className="px-2 py-0.5 rounded bg-surface-container-highest text-[10px] text-on-surface-variant font-bold uppercase tracking-wider">
                Ver 4.2 AI
              </span>
              <span className="px-2 py-0.5 rounded bg-surface-container-highest text-[10px] text-on-surface-variant font-bold uppercase tracking-wider">
                Bovine-Specific
              </span>
            </div>
          </div>
        </section>

        {/* BCS and Wellness Cards */}
        <section className="lg:col-span-5 flex flex-col gap-6">
          <div className="bg-surface-container-low rounded-xl p-8 flex flex-col justify-center items-center text-center relative overflow-hidden group border border-white/5">
            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 blur-3xl -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors"></div>
            <p className="text-xs font-bold tracking-[0.2em] text-slate-400 uppercase mb-4">Calculated BCS</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-7xl font-black text-on-surface tracking-tighter">2.25</h3>
            </div>
            <p className="mt-4 px-4 py-1.5 bg-error-container text-on-error-container rounded-full text-xs font-bold uppercase tracking-wide">
              Under-conditioned
            </p>
            <div className="mt-8 w-full bg-surface-container-lowest h-2 rounded-full overflow-hidden">
              <div className="bg-error h-full" style={{ width: '45%' }}></div>
            </div>
            <div className="w-full flex justify-between mt-2 px-1">
              <span className="text-[10px] text-slate-500 font-bold uppercase">Severe</span>
              <span className="text-[10px] text-slate-500 font-bold uppercase">Optimal</span>
              <span className="text-[10px] text-slate-500 font-bold uppercase">Obese</span>
            </div>
          </div>

          <div className="bg-surface-container-low rounded-xl p-8 border-l-4 border-error/50 border border-white/5">
            <div className="flex items-start justify-between mb-6">
              <div>
                <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
                  Overall Wellness Status
                </p>
                <h4 className="text-2xl font-extrabold text-error tracking-tight mt-1">AT RISK</h4>
              </div>
              <span
                className="material-symbols-outlined text-error text-3xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                warning
              </span>
            </div>
            <div className="bg-surface-container-lowest rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-error/10 flex items-center justify-center flex-shrink-0">
                  <span className="material-symbols-outlined text-error text-xl">thermostat</span>
                </div>
                <div>
                  <p className="text-xs font-bold text-on-surface">Metabolic Stress Detected</p>
                  <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">
                    Detected high probability of ketosis risk due to rapid energy balance shift.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Actionable Management Protocols */}
      <section className="bg-surface-container-low rounded-xl p-8 relative overflow-hidden border border-white/5">
        <div className="flex items-center justify-between mb-8 gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <span className="material-symbols-outlined text-primary text-2xl">assignment_turned_in</span>
            </div>
            <h3 className="text-xl font-bold text-white tracking-tight uppercase">Actionable Management Protocols</h3>
          </div>
          <button className="flex items-center gap-2 text-xs font-bold text-primary uppercase tracking-widest hover:opacity-80 transition-opacity whitespace-nowrap">
            Export PDF
            <span className="material-symbols-outlined text-sm">download</span>
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-surface-container h-full p-6 rounded-lg group hover:bg-surface-container-high transition-colors border border-white/5">
            <div className="flex items-center justify-between mb-4">
              <span className="text-[10px] font-black text-primary uppercase tracking-widest px-2 py-1 bg-primary/5 rounded">
                Immediate
              </span>
              <span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">
                air
              </span>
            </div>
            <p className="text-sm font-semibold text-white leading-relaxed">
              1. Immediate Action: Increase stall ventilation; local THI indicates severe heat stress.
            </p>
          </div>
          <div className="bg-surface-container h-full p-6 rounded-lg group hover:bg-surface-container-high transition-colors border border-white/5">
            <div className="flex items-center justify-between mb-4">
              <span className="text-[10px] font-black text-primary uppercase tracking-widest px-2 py-1 bg-primary/5 rounded">
                Nutrition
              </span>
              <span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">
                restaurant
              </span>
            </div>
            <p className="text-sm font-semibold text-white leading-relaxed">
              2. Feeding: Shift 40% of feed ration to cooler evening hours to minimize digestive metabolic heat.
            </p>
          </div>
          <div className="bg-surface-container h-full p-6 rounded-lg group hover:bg-surface-container-high transition-colors border border-white/5">
            <div className="flex items-center justify-between mb-4">
              <span className="text-[10px] font-black text-primary uppercase tracking-widest px-2 py-1 bg-primary/5 rounded">
                Monitoring
              </span>
              <span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">
                medical_services
              </span>
            </div>
            <p className="text-sm font-semibold text-white leading-relaxed">
              3. Monitoring: Isolate animal to a shaded pen and ensure ad-libitum water access.
            </p>
          </div>
        </div>
        <div className="absolute -bottom-10 -right-10 opacity-5 pointer-events-none">
          <span className="material-symbols-outlined text-[12rem]">verified_user</span>
        </div>
      </section>
    </div>
  )
}
