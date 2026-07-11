import React from 'react'
import { Link } from 'react-router-dom'

export default function AnimalProfileBT8842() {
  const yieldBars = [
    { h: 'h-[60%]', cls: 'bg-primary/20' },
    { h: 'h-[65%]', cls: 'bg-primary/20' },
    { h: 'h-[70%]', cls: 'bg-primary/20' },
    { h: 'h-[62%]', cls: 'bg-primary/20' },
    { h: 'h-[75%]', cls: 'bg-primary/30' },
    { h: 'h-[80%]', cls: 'bg-primary/30' },
    { h: 'h-[78%]', cls: 'bg-primary/40' },
    { h: 'h-[85%]', cls: 'bg-primary/50' },
    { h: 'h-[90%]', cls: 'bg-primary/60', topBorder: true },
    { h: 'h-[82%]', cls: 'bg-primary/40' },
    { h: 'h-[70%]', cls: 'bg-primary/20' },
    { h: 'h-[75%]', cls: 'bg-primary/30' },
    { h: 'h-[88%]', cls: 'bg-primary/50', topBorder: true },
    { h: 'h-[80%]', cls: 'bg-primary/40' },
    { h: 'h-[95%]', cls: 'bg-primary/60', topBorder: true },
  ]

  return (
    <div className="space-y-8">
      {/* Back Button and Title Area */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link
              to="/health/herd-registry"
              className="flex items-center gap-1 text-primary-fixed uppercase text-[10px] font-black tracking-[0.3em] hover:underline"
            >
              <span className="material-symbols-outlined text-xs">arrow_back</span>
              Back to Registry
            </Link>
            <div className="h-px w-12 bg-outline-variant/30"></div>
          </div>
          <h1 className="text-4xl font-black text-on-surface tracking-tighter">ANIMAL PROFILE: #BT-8842</h1>
          <div className="flex flex-wrap gap-2 mt-4">
            {['Friesian', 'Female', '4 Yrs'].map((t) => (
              <span
                key={t}
                className="px-3 py-1 bg-surface-container-highest text-on-surface text-[10px] font-bold tracking-widest rounded uppercase"
              >
                {t}
              </span>
            ))}
            <span className="px-3 py-1 bg-primary-container/20 text-primary text-[10px] font-black tracking-widest rounded border border-primary/30 uppercase flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse"></span>
              HEALTHY
            </span>
          </div>
        </div>
        <div className="flex gap-4">
          <button
            className="px-5 py-2.5 bg-surface-container-highest hover:bg-surface-bright text-primary text-xs font-bold rounded-lg transition-all border border-primary/10"
            type="button"
            aria-label="Secondary action"
          >
            <span className="material-symbols-outlined text-base">download</span>
          </button>
          <button
            className="px-5 py-2.5 bg-primary hover:opacity-90 text-on-primary text-xs font-bold rounded-lg transition-all shadow-lg shadow-primary/20"
            type="button"
          >
            Edit Details
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Visual State & Photo */}
        <div className="col-span-12 lg:col-span-5 bg-surface-container-low rounded-lg overflow-hidden border border-outline-variant/10">
          <div className="relative h-64">
            <img
              alt="Friesian cow close up"
              className="w-full h-full object-cover opacity-80"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuDF_e2KxH96fLwVdKszc2c4hFmgW-q4w16s683d7_9yB1z5Ob1GRS2QTuY0whQjJcZ77Zd6met8Q45dl7_9_6pc6IL-9kONKWf4CbdgoNnBCxm02CYZ2uL56R6_T6RTt8c3-jpOffYcb_tjqO8BXenfopVMbmbXm1RMeA8Gk4IGWmn2K99li1kDj-wOYPyQaea_IXPvhExE0SPjl7MhO7tkHMY8yyESjAltyTREMe-BoOC5PRNGwmK6E1gVxwJed1PTfHsL6_nii"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-surface-container-low via-transparent to-transparent"></div>
            <div className="absolute bottom-6 left-6 right-6 flex items-center justify-between">
              <div>
                <p className="text-[10px] uppercase font-black tracking-widest text-slate-400">Owner Assigned Tag</p>
                <h2 className="text-2xl font-black text-white">#BT-8842</h2>
              </div>
              <div className="flex gap-2">
                <span className="material-symbols-outlined text-primary text-2xl">sensors</span>
                <span className="material-symbols-outlined text-primary text-2xl">visibility</span>
              </div>
            </div>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">Core Parameters</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-surface-container rounded-lg border border-white/5">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Weight</span>
                  <p className="text-xl font-bold mt-1">680 kg</p>
                </div>
                <div className="p-4 bg-surface-container rounded-lg border border-white/5">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Lactation Stage</span>
                  <p className="text-xl font-bold mt-1">Mid (Day 112)</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Analytics & Metrics */}
        <div className="col-span-12 lg:col-span-7 space-y-6">
          {/* Milk Yield Chart Card */}
          <div className="bg-surface-container-low rounded-lg p-6 border border-outline-variant/10">
            <div className="flex justify-between items-center mb-6">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Milk Yield Analytics</h3>
                <p className="text-xs text-slate-500">Weekly tracking and peak yield points</p>
              </div>
              <span className="px-3 py-1 bg-primary/10 text-primary text-[10px] font-bold tracking-widest rounded-full uppercase">
                Avg: 28.5L / Day
              </span>
            </div>
            <div className="flex items-end gap-1.5 h-36 px-2 border-b border-outline-variant/20 pb-2">
              {yieldBars.map((bar, idx) => (
                <div key={idx} className="w-full flex flex-col justify-end h-full">
                  <div className={`w-full rounded-t-sm transition-all ${bar.cls} ${bar.h}`}></div>
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[10px] text-slate-500 font-semibold tracking-wider uppercase mt-4 px-2">
              <span>Mon</span>
              <span>Tue</span>
              <span>Wed</span>
              <span>Thu</span>
              <span>Fri</span>
              <span>Sat</span>
              <span>Sun</span>
            </div>
          </div>

          {/* BCS Trend Info */}
          <div className="bg-surface-container-low rounded-lg p-6 border border-outline-variant/10">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Body Condition Score (BCS) Trend</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-surface-container rounded-lg border border-white/5 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Current Score</span>
                <p className="text-2xl font-black text-primary mt-2">3.75</p>
                <span className="text-[10px] text-slate-400 mt-1">Normal / Healthy</span>
              </div>
              <div className="p-4 bg-surface-container rounded-lg border border-white/5 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Last Scored</span>
                <p className="text-2xl font-black text-slate-300 mt-2">3.50</p>
                <span className="text-[10px] text-slate-400 mt-1">12-May-2024</span>
              </div>
              <div className="p-4 bg-surface-container rounded-lg border border-white/5 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">AI Confidence</span>
                <p className="text-2xl font-black text-secondary mt-2">94%</p>
                <span className="text-[10px] text-slate-400 mt-1">Sentinel Vision</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Historical Assessment Log */}
      <div className="bg-surface-container-low rounded-lg border border-outline-variant/10 overflow-hidden">
        <div className="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight uppercase">Historical Assessment Log</h3>
            <p className="text-xs text-slate-500 mt-0.5">Clinical diagnostics & surveillance record</p>
          </div>
          <button className="px-4 py-2 bg-surface-container hover:bg-surface-container-high text-xs font-bold rounded-lg border border-outline-variant/10 transition-all text-slate-300">
            Export Records
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-lowest/50 text-slate-400 text-[10px] uppercase tracking-[0.2em] font-bold">
                <th className="px-8 py-4">Date</th>
                <th className="px-8 py-4">Assessment Type</th>
                <th className="px-8 py-4">Result / Score</th>
                <th className="px-8 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {[
                {
                  date: 'Oct 24, 2023',
                  iconBg: 'bg-secondary-container/20',
                  iconColor: 'text-secondary',
                  icon: 'psychology',
                  type: 'AI BCS Analysis',
                  resultClass: 'bg-primary/10 text-primary',
                  result: 'Score: 3.75 (Normal)',
                },
                {
                  date: 'Sep 12, 2023',
                  iconBg: 'bg-on-tertiary-fixed-variant/20',
                  iconColor: 'text-tertiary',
                  icon: 'health_and_safety',
                  type: 'Geospatial Heat Stress Analysis',
                  resultClass: 'bg-orange-400/10 text-orange-400',
                  result: 'MODERATE RISK',
                },
                {
                  date: 'Aug 05, 2023',
                  iconBg: 'bg-secondary-container/20',
                  iconColor: 'text-secondary',
                  icon: 'psychology',
                  type: 'Mastitis Thermal Screening',
                  resultClass: 'bg-primary/10 text-primary',
                  result: 'Negative / Clear',
                },
              ].map((row) => (
                <tr key={row.date} className="hover:bg-surface-container-high/20 transition-colors group">
                  <td className="px-8 py-5 text-sm font-medium text-slate-200">{row.date}</td>
                  <td className="px-8 py-5">
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-8 h-8 rounded ${row.iconBg} flex items-center justify-center ${row.iconColor}`}
                      >
                        <span className="material-symbols-outlined text-sm">{row.icon}</span>
                      </div>
                      <span className="text-sm font-semibold text-white">{row.type}</span>
                    </div>
                  </td>
                  <td className="px-8 py-5">
                    <span
                      className={`px-2 py-0.5 ${row.resultClass} text-[10px] font-bold rounded uppercase`}
                    >
                      {row.result}
                    </span>
                  </td>
                  <td className="px-8 py-5 text-right">
                    <div className="flex justify-end gap-3 opacity-40 group-hover:opacity-100 transition-opacity">
                      <button className="text-slate-400 hover:text-primary transition-colors" type="button">
                        <span className="material-symbols-outlined text-lg">visibility</span>
                      </button>
                      <button className="text-slate-400 hover:text-primary transition-colors" type="button">
                        <span className="material-symbols-outlined text-lg">download</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
