import React from 'react'
import { Link } from 'react-router-dom'

export default function WellnessDashboard() {
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
            <div className="px-3 py-1 bg-error-container text-on-error-container rounded text-[10px] font-bold uppercase tracking-wider">
              Moderate Stress
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
                  className="text-primary"
                  cx="64"
                  cy="64"
                  fill="transparent"
                  r="58"
                  stroke="currentColor"
                  strokeDasharray="364.4"
                  strokeDashoffset="91.1"
                  strokeWidth="8"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-black text-on-surface">74</span>
                <span className="text-[10px] uppercase text-slate-400">THI Score</span>
              </div>
            </div>
            <div className="flex-1 space-y-4">
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-medium">
                  <span className="text-slate-400">Ambient Temp</span>
                  <span className="text-on-surface">31.2°C</span>
                </div>
                <div className="w-full h-1 bg-surface-container-highest rounded-full overflow-hidden">
                  <div className="bg-primary w-[75%] h-full"></div>
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-medium">
                  <span className="text-slate-400">Rel. Humidity</span>
                  <span className="text-on-surface">62%</span>
                </div>
                <div className="w-full h-1 bg-surface-container-highest rounded-full overflow-hidden">
                  <div className="bg-primary w-[62%] h-full"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Overview Stats Column */}
        <div className="col-span-12 lg:col-span-7 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-surface-container rounded-xl p-6 flex flex-col justify-between border border-white/5">
            <div className="flex items-center justify-between">
              <span className="material-symbols-outlined text-primary text-2xl">groups</span>
              <span className="material-symbols-outlined text-primary text-sm">trending_up</span>
            </div>
            <div>
              <p className="text-3xl font-black text-on-surface mt-4">1,248</p>
              <p className="text-xs uppercase font-bold tracking-widest text-slate-500 mt-1">
                Registered Cattle
              </p>
            </div>
          </div>
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
              <p className="text-3xl font-black text-on-surface mt-4">1,192</p>
              <p className="text-xs uppercase font-bold tracking-widest text-slate-500 mt-1">
                Healthy
              </p>
            </div>
          </div>
          <div className="bg-surface-container rounded-xl p-6 flex flex-col justify-between border border-white/5">
            <div className="flex items-center justify-between">
              <span className="material-symbols-outlined text-error text-2xl">warning</span>
              <span className="material-symbols-outlined text-error text-sm">trending_down</span>
            </div>
            <div>
              <p className="text-3xl font-black text-on-surface mt-4">56</p>
              <p className="text-xs uppercase font-bold tracking-widest text-slate-500 mt-1">
                At Risk
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Actions (Links to intake and scan) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
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
                  <th className="px-6 py-4">Deviation</th>
                  <th className="px-6 py-4">AI Alert Status</th>
                  <th className="px-6 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-4 font-mono text-xs text-on-surface">#BT-77291</td>
                  <td className="px-6 py-4 font-bold">3.5 / 5.0</td>
                  <td className="px-6 py-4 text-primary text-xs">+0.2 (Optimal)</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-bold uppercase">
                      Stable
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link to="/health/animal-profile-bt-8842" className="material-symbols-outlined text-slate-400 hover:text-primary transition-colors">
                      more_horiz
                    </Link>
                  </td>
                </tr>
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-4 font-mono text-xs text-on-surface">#BT-77298</td>
                  <td className="px-6 py-4 font-bold">2.8 / 5.0</td>
                  <td className="px-6 py-4 text-error text-xs">-0.5 (Critical)</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-error/10 text-error text-[10px] font-bold uppercase">
                      Immediate
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link to="/health/animal-profile-bt-8842" className="material-symbols-outlined text-slate-400 hover:text-primary transition-colors">
                      more_horiz
                    </Link>
                  </td>
                </tr>
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
