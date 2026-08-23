import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

// ─── Simulated AI stream data ────────────────────────────────────────────────
const ANALYSIS_STEPS = [
  { id: 'vision', label: 'Sentinel Vision™ BCS Analysis', icon: 'visibility', delay: 600 },
  { id: 'thermal', label: 'Thermal Stress Index Computation', icon: 'device_thermostat', delay: 1200 },
  { id: 'logs', label: 'Physiological Log Correlation', icon: 'clinical_notes', delay: 1800 },
  { id: 'gps', label: 'Geospatial THI Overlay', icon: 'radar', delay: 2400 },
  { id: 'llm', label: 'Multi-Model LLM Inference Engine', icon: 'psychology', delay: 3100 },
  { id: 'report', label: 'Generating Diagnostic Report', icon: 'summarize', delay: 3800 },
]

const DIAGNOSES = [
  {
    id: 'bcs',
    severity: 'normal',
    icon: 'monitor_weight',
    title: 'Body Condition Score (BCS)',
    score: '3.75 / 5.0',
    badge: 'OPTIMAL',
    badgeCls: 'bg-primary/15 text-primary border border-primary/30',
    detail: 'Vision model detected uniform spinal coverage with balanced hooks and pin visibility. Subcutaneous fat reserves nominal. No wasting or over-conditioning indicators.',
    confidence: 97,
    model: 'Sentinel-Vision-v2.1',
  },
  {
    id: 'thi',
    severity: 'warning',
    icon: 'thermostat',
    title: 'Thermal-Humidity Index (THI)',
    score: '82.4',
    badge: 'MILD STRESS',
    badgeCls: 'bg-orange-400/15 text-orange-400 border border-orange-400/30',
    detail: 'THI of 82.4 indicates the subject is in a mild heat stress zone. Ambient temp 31.4°C and humidity 78% are the contributing factors. Recommend shade access and increased water availability.',
    confidence: 99,
    model: 'GeoTHI-Sentinel v1.4',
  },
  {
    id: 'milk',
    severity: 'normal',
    icon: 'water_drop',
    title: 'Milk Yield Anomaly Detection',
    score: '28.3 L / Day Avg',
    badge: 'STABLE',
    badgeCls: 'bg-primary/15 text-primary border border-primary/30',
    detail: '7-day yield trend shows variance within ±1.8L of baseline. No sub-clinical mastitis indicators detected. Lactation stage mid-phase — normal yield fluctuation expected.',
    confidence: 95,
    model: 'AnomalyNet-Sentinel v3.0',
  },
  {
    id: 'temp',
    severity: 'normal',
    icon: 'health_and_safety',
    title: 'Body Temperature Trend',
    score: '38.53°C Avg',
    badge: 'NORMAL',
    badgeCls: 'bg-primary/15 text-primary border border-primary/30',
    detail: 'Core temperature readings over 7 days remain within the bovine euthermia range (38.0–39.0°C). No pyrexia indicators present.',
    confidence: 98,
    model: 'VitalSense-AI v2.0',
  },
]

const SEVERITY_BAR = { normal: 'bg-primary', warning: 'bg-orange-400', critical: 'bg-error' }

// ─── Component ───────────────────────────────────────────────────────────────
export default function SmartDiagnosticsPage() {
  const [completedSteps, setCompletedSteps] = useState([])
  const [analysisComplete, setAnalysisComplete] = useState(false)
  const [activeTab, setActiveTab] = useState('bcs')

  useEffect(() => {
    ANALYSIS_STEPS.forEach((step) => {
      setTimeout(() => {
        setCompletedSteps((prev) => [...prev, step.id])
      }, step.delay)
    })
    setTimeout(() => setAnalysisComplete(true), 4200)
  }, [])

  const activeResult = DIAGNOSES.find((d) => d.id === activeTab) ?? DIAGNOSES[0]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <Link
            to="/health/7-day-triage-scan"
            className="flex items-center gap-1 text-primary-fixed uppercase text-[10px] font-black tracking-[0.3em] hover:underline"
          >
            <span className="material-symbols-outlined text-xs">arrow_back</span>
            Back to Triage Intake
          </Link>
          <div className="h-px w-12 bg-outline-variant/30" />
        </div>
        <p className="text-primary text-xs font-black tracking-[0.3em] uppercase opacity-80 mt-2">
          Phase 02: AI Analysis
        </p>
        <h2 className="text-4xl font-black text-on-surface tracking-tighter uppercase font-headline">
          Smart <span className="text-primary">AI</span> Multimodal Diagnostics
        </h2>
        <div className="h-1 w-24 bg-gradient-to-r from-primary to-transparent mt-1" />
      </div>

      {/* Subject Info Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-surface-container-low rounded-xl px-6 py-4 border border-white/5">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
              pets
            </span>
          </div>
          <div>
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Subject</p>
            <p className="text-base font-black text-white">#BT-8842 — Friesian Female, 4 Yrs</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${
              analysisComplete
                ? 'bg-primary/10 text-primary border-primary/30'
                : 'bg-orange-400/10 text-orange-400 border-orange-400/30 animate-pulse'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
            {analysisComplete ? 'Analysis Complete' : 'Processing…'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Analysis Progress Panel */}
        <div className="lg:col-span-4">
          <div className="bg-surface-container-low rounded-xl border border-white/5 overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant/10">
              <h3 className="text-sm font-black uppercase tracking-widest text-on-surface">AI Engine Activity</h3>
              <p className="text-[10px] text-slate-500 mt-0.5">Sentinel Multimodal Stack v4.2</p>
            </div>
            <div className="p-6 space-y-4">
              {ANALYSIS_STEPS.map((step) => {
                const done = completedSteps.includes(step.id)
                return (
                  <div key={step.id} className="flex items-center gap-4">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500 ${
                        done
                          ? 'bg-primary/20 text-primary shadow-[0_0_12px_rgba(78,222,163,0.3)]'
                          : 'bg-surface-container-highest text-slate-600'
                      }`}
                    >
                      {done ? (
                        <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                          check_circle
                        </span>
                      ) : (
                        <span className="material-symbols-outlined text-sm">{step.icon}</span>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p
                        className={`text-xs font-bold truncate transition-colors duration-500 ${
                          done ? 'text-on-surface' : 'text-slate-600'
                        }`}
                      >
                        {step.label}
                      </p>
                      {done && (
                        <p className="text-[9px] text-primary uppercase tracking-widest mt-0.5 font-black">
                          ✓ Done
                        </p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Overall status progress bar */}
            <div className="px-6 pb-6">
              <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-2">
                <span>Overall Progress</span>
                <span className="text-primary">
                  {Math.round((completedSteps.length / ANALYSIS_STEPS.length) * 100)}%
                </span>
              </div>
              <div className="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-700 shadow-[0_0_8px_rgba(78,222,163,0.5)]"
                  style={{ width: `${(completedSteps.length / ANALYSIS_STEPS.length) * 100}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Diagnostic Results Panel */}
        <div className="lg:col-span-8 space-y-6">
          {/* Tab Switcher */}
          <div className="flex flex-wrap gap-2">
            {DIAGNOSES.map((d) => (
              <button
                key={d.id}
                onClick={() => setActiveTab(d.id)}
                disabled={!analysisComplete}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all border ${
                  activeTab === d.id && analysisComplete
                    ? 'bg-primary text-on-primary border-transparent shadow-lg shadow-primary/20'
                    : analysisComplete
                    ? 'bg-surface-container-low text-slate-400 border-white/5 hover:border-primary/30 hover:text-primary'
                    : 'bg-surface-container-lowest text-slate-700 border-white/5 cursor-not-allowed'
                }`}
              >
                <span className="material-symbols-outlined text-sm">{d.icon}</span>
                {d.title.split(' ')[0]}
              </button>
            ))}
          </div>

          {/* Result Card */}
          {analysisComplete ? (
            <div className="bg-surface-container-low rounded-xl border border-white/5 overflow-hidden">
              {/* Card Header */}
              <div className="relative px-8 py-6 border-b border-outline-variant/10 overflow-hidden">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(78,222,163,0.05),transparent_60%)]" />
                <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                      <span
                        className="material-symbols-outlined text-primary text-2xl"
                        style={{ fontVariationSettings: "'FILL' 1" }}
                      >
                        {activeResult.icon}
                      </span>
                    </div>
                    <div>
                      <h3 className="text-lg font-black text-white">{activeResult.title}</h3>
                      <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                        Model: {activeResult.model}
                      </p>
                    </div>
                  </div>
                  <span className={`px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest ${activeResult.badgeCls}`}>
                    {activeResult.badge}
                  </span>
                </div>
              </div>

              {/* Card Body */}
              <div className="px-8 py-6 space-y-6">
                {/* Score */}
                <div className="flex items-baseline gap-4">
                  <span className="text-5xl font-black text-primary font-display tracking-tight">
                    {activeResult.score}
                  </span>
                </div>

                {/* Confidence Bar */}
                <div>
                  <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-2">
                    <span>AI Confidence</span>
                    <span className="text-primary">{activeResult.confidence}%</span>
                  </div>
                  <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-1000 ${SEVERITY_BAR[activeResult.severity]}`}
                      style={{ width: `${activeResult.confidence}%` }}
                    />
                  </div>
                </div>

                {/* Detail */}
                <div className="bg-surface-container-lowest/60 rounded-xl p-5 border border-outline-variant/10">
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">
                    AI Interpretation
                  </p>
                  <p className="text-sm text-slate-300 leading-relaxed">{activeResult.detail}</p>
                </div>
              </div>
            </div>
          ) : (
            /* Skeleton while processing */
            <div className="bg-surface-container-low rounded-xl border border-white/5 overflow-hidden animate-pulse">
              <div className="px-8 py-6 border-b border-outline-variant/10">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-surface-container-highest" />
                  <div className="space-y-2 flex-1">
                    <div className="h-4 bg-surface-container-highest rounded w-1/2" />
                    <div className="h-3 bg-surface-container-highest rounded w-1/3" />
                  </div>
                </div>
              </div>
              <div className="px-8 py-6 space-y-6">
                <div className="h-10 bg-surface-container-highest rounded w-1/3" />
                <div className="space-y-2">
                  <div className="h-2 bg-surface-container-highest rounded w-full" />
                  <div className="h-2 bg-surface-container-highest rounded w-5/6" />
                </div>
                <div className="h-24 bg-surface-container-highest rounded-xl" />
              </div>
            </div>
          )}

          {/* All-Clear Summary */}
          {analysisComplete && (
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-surface-container-low rounded-xl px-6 py-5 border border-primary/20 relative overflow-hidden">
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_left,rgba(78,222,163,0.05),transparent_60%)]" />
              <div className="relative flex items-center gap-4">
                <span
                  className="material-symbols-outlined text-primary text-3xl"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  verified
                </span>
                <div>
                  <p className="text-sm font-black text-white">Overall Wellness Assessment</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">
                    1 Mild Alert · 3 Modules Normal · Immediate intervention not required
                  </p>
                </div>
              </div>
              <div className="relative flex gap-3">
                <Link
                  to="/health/ai-wellness-report"
                  className="flex items-center gap-2 bg-primary text-on-primary px-5 py-2.5 rounded-lg text-xs font-black uppercase tracking-widest shadow-lg shadow-primary/20 hover:opacity-90 transition-all"
                >
                  <span className="material-symbols-outlined text-sm">description</span>
                  Full Report
                </Link>
                <button
                  className="flex items-center gap-2 bg-surface-container-highest hover:bg-surface-bright text-slate-300 px-4 py-2.5 rounded-lg text-xs font-black uppercase tracking-widest border border-white/5 transition-all"
                  type="button"
                >
                  <span className="material-symbols-outlined text-sm">download</span>
                  Export PDF
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
