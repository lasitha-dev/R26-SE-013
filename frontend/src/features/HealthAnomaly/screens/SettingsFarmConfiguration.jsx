import React from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function SettingsFarmConfiguration() {
  const navigate = useNavigate()

  const handleSave = () => {
    // In a real application, you would save options here.
    // For now, redirect to the dashboard.
    navigate('/health/dashboard')
  }

  return (
    <div className="space-y-8">
      {/* Title Bar */}
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
        <h2 className="text-4xl font-extrabold tracking-tight text-on-surface mt-2 mb-2 font-headline">
          SYSTEM CONFIGURATION <span className="text-primary">&amp;</span> SETTINGS
        </h2>
        <div className="h-1 w-24 bg-primary rounded-full mt-1"></div>
      </div>

      {/* Main Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Farm Details Card */}
        <div className="bg-surface-container-low p-8 rounded-xl relative overflow-hidden group border border-white/5">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <span className="material-symbols-outlined text-6xl">agriculture</span>
          </div>
          <h3 className="text-lg font-bold text-primary mb-6 flex items-center gap-2">
            <span className="material-symbols-outlined text-base">info</span>
            Farm Details
          </h3>
          <div className="space-y-4">
            {[
              { label: 'Farm Name / REG NO.', type: 'text', value: 'Sentinel Dairy / REG-AI-9902' },
              { label: 'Owner Full Name', type: 'text', value: 'Dr. Julian Vane' },
              { label: 'Email Address', type: 'email', value: 'vane.j@sentinel-ai.vet' },
              { label: 'Location District', type: 'text', value: 'Kurunegala District' },
              { label: 'Veterinarian Contact', type: 'text', value: 'Dr. Kamal / 077xxxxxxx' },
            ].map((field) => (
              <div key={field.label} className="space-y-1">
                <label className="text-[0.7rem] font-bold tracking-[0.1em] text-on-surface-variant uppercase">
                  {field.label}
                </label>
                <input
                  className="w-full bg-surface-container-lowest border-outline-variant/20 focus:border-primary border rounded-lg px-4 py-2 text-on-surface focus:ring-0 transition-all outline-none text-sm"
                  type={field.type}
                  defaultValue={field.value}
                />
              </div>
            ))}
          </div>
        </div>

        {/* AI Thresholds Card */}
        <div className="bg-surface-container-low p-8 rounded-xl relative overflow-hidden group border border-white/5">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <span className="material-symbols-outlined text-6xl">monitoring</span>
          </div>
          <h3 className="text-lg font-bold text-primary mb-6 flex items-center gap-2">
            <span className="material-symbols-outlined text-base">vitals</span>
            AI Alert Thresholds
          </h3>
          <div className="space-y-8">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-[0.7rem] font-bold tracking-[0.1em] text-on-surface-variant uppercase">
                  Critical THI Alert Level
                </label>
                <span className="text-primary font-bold text-lg">78</span>
              </div>
              <input
                className="w-full h-1.5 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary"
                min="60"
                max="90"
                type="range"
                defaultValue="78"
              />
              <div className="flex justify-between text-[0.6rem] text-on-surface-variant">
                <span>60 (Low Risk)</span>
                <span>90 (Severe Stress)</span>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-[0.7rem] font-bold tracking-[0.1em] text-on-surface-variant uppercase">
                  DAILY MILK DROP WARNING
                </label>
                <span className="text-primary font-bold text-lg">2.0 L</span>
              </div>
              <input
                className="w-full h-1.5 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary"
                min="0"
                max="1"
                step="0.05"
                type="range"
                defaultValue="0.25"
              />
              <p className="text-[0.7rem] text-on-surface-variant mt-2">
                Triggers alert if daily yield drops by this amount
              </p>
            </div>

            <div className="flex justify-between items-center pt-2">
              <div>
                <p className="text-sm font-bold text-on-surface">Automated Heat Stress Notifications</p>
                <p className="text-[0.7rem] text-on-surface-variant">Push alerts to mobile devices</p>
              </div>
              <button className="w-12 h-6 bg-primary rounded-full relative transition-colors duration-300" type="button">
                <span className="absolute right-1 top-1 w-4 h-4 bg-on-primary rounded-full shadow-md"></span>
              </button>
            </div>
          </div>
        </div>

        {/* Security & Access Card */}
        <div className="md:col-span-2 bg-surface-container-low p-8 rounded-xl border border-white/5">
          <h3 className="text-lg font-bold text-primary mb-8 flex items-center gap-2">
            <span className="material-symbols-outlined text-base">security</span>
            Data &amp; Security
          </h3>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-center">
            <div className="space-y-4">
              <button
                className="w-full flex items-center justify-center gap-3 bg-surface-container-highest hover:bg-surface-bright text-primary font-bold py-4 px-6 rounded-lg transition-all active:scale-95"
                type="button"
              >
                <span className="material-symbols-outlined">download</span>
                Export Farm Data (CSV)
              </button>
              <button
                className="w-full flex items-center justify-center gap-3 bg-surface-container-highest hover:bg-surface-bright text-primary font-bold py-4 px-6 rounded-lg transition-all active:scale-95"
                type="button"
              >
                <span className="material-symbols-outlined">lock_person</span>
                Manage Access Protocols
              </button>
            </div>
            <div className="lg:col-span-2 bg-surface-container-lowest/50 p-6 rounded-lg border border-outline-variant/10">
              <div className="flex items-center gap-4">
                <div className="bg-primary/10 p-3 rounded-full">
                  <span
                    className="material-symbols-outlined text-primary"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    cloud_done
                  </span>
                </div>
                <div>
                  <p className="text-sm font-bold text-on-surface">
                    Cloud Sync Status: <span className="text-primary">Synced</span>
                  </p>
                  <p className="text-[0.7rem] text-on-surface-variant mt-0.5">Last encrypted backup: 2 mins ago</p>
                </div>
              </div>
              <div className="mt-6 h-1 w-full bg-surface-container-highest rounded-full overflow-hidden">
                <div className="h-full bg-primary w-full shadow-[0_0_10px_rgba(78,222,163,0.5)]"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Save Button */}
      <div className="flex justify-end pt-4">
        <button
          onClick={handleSave}
          className="flex items-center gap-3 bg-gradient-to-br from-primary to-primary-container text-on-primary-container px-8 py-4 rounded-xl font-black text-sm tracking-widest uppercase shadow-[0_10px_40px_rgba(16,185,129,0.3)] hover:shadow-[0_15px_50px_rgba(16,185,129,0.5)] hover:-translate-y-0.5 transition-all active:scale-95"
          type="button"
        >
          <span className="material-symbols-outlined">save</span>
          Save Configurations
        </button>
      </div>
    </div>
  )
}
