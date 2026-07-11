import React from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function WellnessDataIntake() {
  const navigate = useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault()
    // In a real application, you would handle API submission here.
    // For now, we will navigate back to the dashboard.
    navigate('/health/dashboard')
  }

  return (
    <div className="flex justify-center min-h-[calc(100vh-8rem)]">
      <div className="max-w-4xl w-full space-y-12">
        {/* Header Title */}
        <div className="bg-surface-container-high rounded-2xl p-6 md:p-10 border border-outline-variant/10 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <span className="material-symbols-outlined text-[150px] text-primary">edit_note</span>
          </div>

          <div className="relative space-y-8">
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
              <h2 className="text-3xl font-black text-white tracking-tight uppercase">Wellness Data Intake</h2>
              <p className="text-sm text-slate-400 mt-2 font-medium">
                Log clinical vital signs and daily metrics for early diagnostics.
              </p>
            </header>

            <form className="space-y-6" onSubmit={handleSubmit}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                    Select Subject (Cattle ID / Tag)
                  </label>
                  <div className="relative">
                    <select
                      className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-lg font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                      defaultValue=""
                      required
                    >
                      <option disabled value="">
                        Choose Bovine Unit
                      </option>
                      <option value="bt8842">#BT-8842 (Friesian)</option>
                      <option value="sudu">Sudu (Jersey)</option>
                      <option value="bt7729">#BT-7729 (Sahiwal)</option>
                      <option value="maanam">Maanam (Local)</option>
                    </select>
                    <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                      expand_more
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                    Daily Milk Yield (Liters)
                  </label>
                  <div className="relative">
                    <input
                      className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-2xl font-display font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                      placeholder="00.0"
                      type="number"
                      step="0.1"
                      required
                    />
                    <span className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-600 font-bold">
                      LITERS
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                  Body Weight Before Milking (kg)
                </label>
                <div className="relative">
                  <input
                    className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-2xl font-display font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                    placeholder="000"
                    type="number"
                    required
                  />
                  <span className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-600 font-bold">
                    KG
                  </span>
                </div>
              </div>

              <div className="bg-primary-container/5 border border-primary-container/10 rounded-lg p-4 flex items-start gap-4">
                <span
                  className="material-symbols-outlined text-primary mt-0.5"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  info
                </span>
                <p className="text-sm text-primary-container font-medium leading-relaxed">
                  Continuous daily logging enables the AI to detect sub-clinical health anomalies early.
                  <span className="text-[10px] block mt-1 text-primary/60 font-normal uppercase tracking-widest">
                    Protocol: VET-SEC-09
                  </span>
                </p>
              </div>

              <button
                className="w-full h-16 rounded-xl bg-gradient-to-br from-primary-container to-primary text-on-primary-container font-black text-lg tracking-[0.2em] uppercase shadow-xl shadow-primary/20 hover:scale-[1.01] active:scale-[0.98] transition-all flex items-center justify-center gap-3"
                type="submit"
              >
                <span>Save Daily Log</span>
                <span className="material-symbols-outlined">send</span>
              </button>
            </form>
          </div>
        </div>

        {/* Sync Metadata Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-surface-container-low rounded-lg p-5 flex flex-col border border-white/5">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
              Last Sync
            </span>
            <span className="text-white font-medium">Today, 06:45 AM</span>
            <div className="mt-4 h-1 w-full bg-surface-container-lowest rounded-full overflow-hidden">
              <div className="h-full bg-primary w-full"></div>
            </div>
          </div>
          <div className="bg-surface-container-low rounded-lg p-5 flex flex-col border border-white/5">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
              Active Monitors
            </span>
            <span className="text-white font-medium">1,240 Bovine Units</span>
            <div className="mt-4 h-1 w-full bg-surface-container-lowest rounded-full overflow-hidden">
              <div className="h-full bg-primary w-4/5"></div>
            </div>
          </div>
          <div className="bg-surface-container-low rounded-lg p-5 flex flex-col border border-white/5">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
              AI Confidence
            </span>
            <span className="text-primary font-medium">99.2% Accuracy</span>
            <div className="mt-4 h-1 w-full bg-surface-container-lowest rounded-full overflow-hidden">
              <div className="h-full bg-primary w-[99%]"></div>
            </div>
          </div>
        </div>

        {/* Visual Watermark Area */}
        <div className="w-full h-48 rounded-2xl overflow-hidden relative">
          <img
            alt="Smart Agriculture Visualization"
            className="w-full h-full object-cover opacity-40"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuDkvUDaJg44xyJ5Zil1vXCT8hhmKzS16Axr2Xjruc546_R6q6Gj4Fmy1CpVkYunWbW1arWFk4t6W4VUzUKp0Hs_wjrPOaeGBMwgioRJuYGWE_svJi0Xui4BxOL4jA7NIibinsXIx0tI_ygu5RLHk6zBQpiVUzrmvVF4tlW9bnTomlxlg6Lco1AOf2zd1k1ENAAiMjWe6k7fC1ShOaGzIHxW0iItCbEl1_0nOElHPJl5HRrteC-c5cWR35dwNfQs4eDyPKDhzuba1Enf"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent"></div>
          <div className="absolute bottom-6 left-8">
            <p className="text-primary font-bold text-lg">System Status: Optimal</p>
            <p className="text-slate-400 text-sm">
              All bio-telemetry nodes reporting nominal activity.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
