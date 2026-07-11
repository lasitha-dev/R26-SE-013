import React from 'react'
import { Link } from 'react-router-dom'

export default function HerdRegistry() {
  const statusStyles = {
    primary: {
      pill: 'bg-primary/10 text-primary',
      dot: 'bg-primary',
    },
    error: {
      pill: 'bg-error/10 text-error',
      dot: 'bg-error',
    },
  }

  const rows = [
    {
      id: '#BT-8842',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '12-May-2020 (4 Yrs)',
      breed: 'Friesian',
      status: { label: 'Healthy', color: 'primary', pulse: false },
    },
    {
      id: 'Sudu',
      dot: 'bg-error',
      gender: 'Male',
      dob: '05-Jan-2021 (3 Yrs)',
      breed: 'Jersey',
      status: { label: 'At Risk', color: 'error', pulse: true },
    },
    {
      id: '#BT-7729',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '20-Oct-2019 (5 Yrs)',
      breed: 'Sahiwal',
      status: { label: 'Healthy', color: 'primary', pulse: false },
    },
    {
      id: 'Maanam',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '15-Mar-2022 (2 Yrs)',
      breed: 'Local',
      status: { label: 'Healthy', color: 'primary', pulse: false },
    },
  ]

  return (
    <div className="space-y-8">
      {/* Title Bar with Add Button */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-black tracking-tight text-white uppercase">HERD REGISTRY</h2>
          <div className="flex items-center gap-4 text-slate-400 text-xs tracking-widest uppercase font-medium">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-primary rounded-full"></span> 42 Total Livestock
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full"></span> 98% Bio-Security Score
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-error rounded-full"></span> 1 Pending Alert
            </span>
          </div>
        </div>
        <Link
          to="/health/add-new-animal"
          className="self-start sm:self-auto px-6 py-3 bg-primary-container text-on-primary-container font-bold rounded-lg flex items-center gap-2 hover:opacity-90 transition-all active:scale-[0.98]"
        >
          <span className="material-symbols-outlined">add</span>
          Add New Animal
        </Link>
      </div>

      {/* Population & Breed Grid */}
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8 bg-surface-container-low rounded-xl p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
            <span className="material-symbols-outlined text-[120px] text-primary">analytics</span>
          </div>
          <div className="relative z-10">
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-6">Population Health Trends</h3>
            <div className="flex items-end gap-2 h-32 px-2">
              {[60, 75, 55, 90, 85, 95].map((h, idx) => (
                <div
                  key={idx}
                  className="w-full bg-primary/20 rounded-t hover:bg-primary/40 transition-all"
                  style={{ height: `${h}%` }}
                ></div>
              ))}
              <div className="w-full bg-primary rounded-t hover:bg-primary/80 transition-all relative" style={{ height: '80%' }}>
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-surface text-primary text-[10px] font-bold px-2 py-1 rounded border border-primary/20 whitespace-nowrap">
                  OPT-MAX
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 bg-surface-container-low rounded-xl p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Breed Composition</h3>
            <p className="text-xs text-slate-500">Distribution analysis across primary herds</p>
          </div>
          <div className="space-y-3 mt-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Friesian</span>
              <span className="text-xs font-bold text-primary">64%</span>
            </div>
            <div className="w-full h-1 bg-surface rounded-full overflow-hidden">
              <div className="h-full bg-primary w-[64%]"></div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Jersey</span>
              <span className="text-xs font-bold text-secondary">22%</span>
            </div>
            <div className="w-full h-1 bg-surface rounded-full overflow-hidden">
              <div className="h-full bg-secondary w-[22%]"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Active Registry Table */}
      <div className="bg-surface-container-low rounded-xl overflow-hidden">
        <div className="px-8 py-6 flex items-center justify-between border-b border-surface/50">
          <h3 className="text-lg font-bold text-white tracking-tight">Active Animal Registry</h3>
          <div className="flex items-center gap-2">
            <button
              className="p-2 hover:bg-surface-container-high rounded transition-colors text-slate-400"
              type="button"
            >
              <span className="material-symbols-outlined">filter_list</span>
            </button>
            <button
              className="p-2 hover:bg-surface-container-high rounded transition-colors text-slate-400"
              type="button"
            >
              <span className="material-symbols-outlined">download</span>
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-lowest/50 text-slate-400 text-[10px] uppercase tracking-[0.2em] font-bold">
                <th className="px-8 py-4">Identifier (Tag / Name)</th>
                <th className="px-6 py-4">Gender</th>
                <th className="px-6 py-4">DOB &amp; Age</th>
                <th className="px-6 py-4">Breed</th>
                <th className="px-6 py-4">Current Health Status</th>
                <th className="px-8 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface/30">
              {rows.map((r) => (
                <tr key={r.id} className="group hover:bg-surface-container-high/30 transition-colors">
                  <td className="px-8 py-5">
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${r.dot}`}></span>
                      <span className="font-mono text-sm font-bold text-white">{r.id}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span className="text-sm text-on-surface/80">{r.gender}</span>
                  </td>
                  <td className="px-6 py-5">
                    <span className="text-sm font-medium text-on-surface/80 whitespace-nowrap">{r.dob}</span>
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-slate-500 text-lg">category</span>
                      <span className="text-sm">{r.breed}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full ${statusStyles[r.status.color].pill} text-[10px] font-bold uppercase tracking-wider`}
                    >
                      <span
                        className={`w-1 h-1 rounded-full ${statusStyles[r.status.color].dot} ${r.status.pulse ? 'animate-pulse' : ''}`}
                      ></span>
                      {r.status.label}
                    </span>
                  </td>
                  <td className="px-8 py-5 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <Link
                        to="/health/animal-profile-bt-8842"
                        className="p-2 text-slate-400 hover:text-primary transition-colors hover:bg-primary/5 rounded-lg"
                      >
                        <span className="material-symbols-outlined text-xl">visibility</span>
                      </Link>
                      <button
                        className="p-2 text-slate-400 hover:text-secondary transition-colors hover:bg-secondary/5 rounded-lg"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-xl">edit</span>
                      </button>
                      <button
                        className="p-2 text-slate-400 hover:text-error transition-colors hover:bg-error/5 rounded-lg"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-xl">delete</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="px-8 py-4 bg-surface-container-lowest/30 flex items-center justify-between">
          <p className="text-xs text-slate-500 font-medium">
            Showing <span className="text-on-surface">4</span> of <span className="text-on-surface">42</span> tracked animals
          </p>
          <div className="flex items-center gap-2">
            <button className="p-1.5 hover:bg-surface-container-high rounded-lg text-slate-400 transition-colors" type="button">
              <span className="material-symbols-outlined text-lg">chevron_left</span>
            </button>
            <div className="flex gap-1">
              <button className="w-8 h-8 rounded-lg bg-primary/10 text-primary text-xs font-bold border border-primary/20" type="button">
                1
              </button>
              <button className="w-8 h-8 rounded-lg hover:bg-surface-container-high text-slate-400 text-xs font-bold transition-colors" type="button">
                2
              </button>
              <button className="w-8 h-8 rounded-lg hover:bg-surface-container-high text-slate-400 text-xs font-bold transition-colors" type="button">
                3
              </button>
            </div>
            <button className="p-1.5 hover:bg-surface-container-high rounded-lg text-slate-400 transition-colors" type="button">
              <span className="material-symbols-outlined text-lg">chevron_right</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
