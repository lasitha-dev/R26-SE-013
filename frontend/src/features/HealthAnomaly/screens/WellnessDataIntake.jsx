export default function WellnessDataIntake() {
  return (
    <div className="flex min-h-screen overflow-hidden bg-background text-on-surface">
      <aside className="h-screen w-64 fixed left-0 top-0 bg-[#131b2e] border-r border-emerald-500/10 flex flex-col py-6 tracking-tight z-50">
        <div className="px-6 mb-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-500 rounded flex items-center justify-center">
              <span
                className="material-symbols-outlined text-on-primary text-xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                shield
              </span>
            </div>
            <div>
              <h1 className="text-white font-black tracking-widest leading-none">ADRS CORE</h1>
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mt-1">
                CLINICAL PRECISION
              </p>
            </div>
          </div>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          <a
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:text-emerald-200 hover:bg-emerald-500/10 transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined text-[20px]">pets</span>
            <span className="text-sm">Herd Registry</span>
          </a>
          <a
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-emerald-400 font-bold border-r-2 border-emerald-500 bg-emerald-500/5 transition-all duration-200"
            href="#"
          >
            <span
              className="material-symbols-outlined text-[20px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              health_and_safety
            </span>
            <span className="text-sm">Wellness &amp; BCS</span>
          </a>
          <a
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:text-emerald-200 hover:bg-emerald-500/10 transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined text-[20px]">memory</span>
            <span className="text-sm">AI Smart Diagnosis</span>
          </a>
          <a
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:text-emerald-200 hover:bg-emerald-500/10 transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined text-[20px]">map</span>
            <span className="text-sm">Geospatial Intelligence</span>
          </a>
          <a
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:text-emerald-200 hover:bg-emerald-500/10 transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined text-[20px]">cloudy_snowing</span>
            <span className="text-sm">Seasonal Forecasting</span>
          </a>
        </nav>
        <div className="px-4 pb-6 mt-auto space-y-6">
          <div className="space-y-1">
            <a
              className="flex items-center gap-3 px-4 py-2 text-slate-400 hover:text-emerald-200 transition-colors"
              href="#"
            >
              <span className="material-symbols-outlined text-[20px]">settings</span>
              <span className="text-sm">Settings</span>
            </a>
            <a
              className="flex items-center gap-3 px-4 py-2 text-slate-400 hover:text-emerald-200 transition-colors"
              href="#"
            >
              <span className="material-symbols-outlined text-[20px]">help</span>
              <span className="text-sm">Support</span>
            </a>
          </div>
        </div>
      </aside>

      <main className="flex-grow ml-64 min-h-screen flex flex-col relative">
        <header className="fixed top-0 right-0 w-[calc(100%-16rem)] h-16 bg-[#0b1326] flex items-center justify-between px-8 z-40 border-none">
          <div className="flex items-center flex-grow max-w-xl">
            <div className="relative w-full">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xl">
                search
              </span>
              <input
                className="w-full bg-surface-container-lowest border-none rounded-full py-2 pl-11 pr-4 text-sm text-on-surface focus:ring-1 focus:ring-primary-container transition-all"
                placeholder="Search records, cows, or diagnostics..."
                type="text"
              />
            </div>
          </div>
          <div className="flex items-center gap-6">
            <button className="text-slate-300 hover:bg-[#171f33] p-2 rounded-full transition-opacity active:opacity-80">
              <span className="material-symbols-outlined">notifications</span>
            </button>
            <button className="text-slate-300 hover:bg-[#171f33] p-2 rounded-full transition-opacity active:opacity-80">
              <span className="material-symbols-outlined">apps</span>
            </button>
            <div className="flex items-center gap-3 ml-2 border-l border-surface-container-high pl-6">
              <div className="text-right">
                <p className="text-xs font-bold text-on-surface">Kamal Perera</p>
                <p className="text-[10px] text-slate-500">Dairy Farmer</p>
              </div>
              <img
                alt="User Profile"
                className="w-10 h-10 rounded-full object-cover border-2 border-primary-container/20"
                data-alt="A professional headshot of a senior veterinarian with short dark hair and a kind expression, wearing a navy blue medical scrub. The portrait is set against a clean, softly lit clinical background with deep navy and subtle green ambient lighting, reflecting a modern and authoritative atmosphere in a high-tech medical environment."
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuBndLehRQGFxr8pqniPQCr-EumwCFCC8JQESauxm9ACvzauz3vjyf-hPoOONV5dZjUPNCS6-tNbkjMUjz_C36bApd0AVGXohw5PnkwNBOYxIYNURS6m6HEtmFmjsLOZ96U3Yad6U0WasoSvdUGaQNkW5Ss9OC971fmYZe08EAl_XcVwSITf6NIcHbnPfbmwVRC79793hKV6cwWltGw8cX2_JmzLs3p2pr8cuv35sYiVPxcPmXAiq8k-YgimKZUciQAIACV5YKwLF4EZ"
              />
            </div>
          </div>
        </header>

        <div className="mt-16 p-10 flex flex-col flex-grow overflow-y-auto no-scrollbar">
          <div className="max-w-4xl mx-auto w-full">
            <div className="mb-10 flex items-center gap-4">
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <h2 className="text-2xl font-black text-white tracking-widest uppercase">
                    Wellness Data Intake
                  </h2>
                  <div className="w-2 h-2 rounded-full bg-primary animate-pulse"></div>
                </div>
                <div className="h-1 w-24 bg-gradient-to-r from-primary to-transparent mt-1"></div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-8">
              <div className="bg-surface-container-high rounded-xl p-8 shadow-2xl relative overflow-hidden">
                <div
                  className="absolute inset-0 opacity-5 pointer-events-none"
                  style={{
                    backgroundImage: 'radial-gradient(#4edea3 0.5px, transparent 0.5px)',
                    backgroundSize: '20px 20px'
                  }}
                ></div>

                <form className="relative z-10 space-y-8">
                  <div className="space-y-2">
                    <label className="text-[11px] font-bold tracking-widest text-primary uppercase flex items-center gap-2">
                      <span className="material-symbols-outlined text-sm">tag</span>
                      Select Cow Tag ID
                    </label>
                    <div className="relative group">
                      <select
                        className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-on-surface appearance-none focus:ring-1 focus:ring-primary focus:border-primary transition-all cursor-pointer"
                        defaultValue=""
                      >
                        <option value="" disabled>
                          Search by ID or Name...
                        </option>
                        <option value="402">ID: #402 - &quot;Bessie&quot;</option>
                        <option value="511">ID: #511 - &quot;Luna&quot;</option>
                        <option value="398">ID: #398 - &quot;Daisy&quot;</option>
                        <option value="122">ID: #122 - &quot;Clover&quot;</option>
                      </select>
                      <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">
                        expand_more
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div className="space-y-2">
                      <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                        Morning Milk Yield (Liters)
                      </label>
                      <div className="relative">
                        <input
                          className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-2xl font-display font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                          placeholder="0.0"
                          step="0.1"
                          type="number"
                        />
                        <span className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-600 font-bold">
                          L
                        </span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                        Evening Milk Yield (Liters)
                      </label>
                      <div className="relative">
                        <input
                          className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-4 px-5 text-2xl font-display font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                          placeholder="0.0"
                          step="0.1"
                          type="number"
                        />
                        <span className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-600 font-bold">
                          L
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
                    type="button"
                  >
                    <span>Save Daily Log</span>
                    <span className="material-symbols-outlined">send</span>
                  </button>
                </form>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-surface-container rounded-lg p-5 flex flex-col">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
                    Last Sync
                  </span>
                  <span className="text-white font-medium">Today, 06:45 AM</span>
                  <div className="mt-4 h-1 w-full bg-surface-container-lowest rounded-full overflow-hidden">
                    <div className="h-full bg-primary w-full"></div>
                  </div>
                </div>
                <div className="bg-surface-container rounded-lg p-5 flex flex-col">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
                    Active Monitors
                  </span>
                  <span className="text-white font-medium">1,240 Bovine Units</span>
                  <div className="mt-4 h-1 w-full bg-surface-container-lowest rounded-full overflow-hidden">
                    <div className="h-full bg-primary w-4/5"></div>
                  </div>
                </div>
                <div className="bg-surface-container rounded-lg p-5 flex flex-col">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
                    AI Confidence
                  </span>
                  <span className="text-primary font-medium">99.2% Accuracy</span>
                  <div className="mt-4 h-1 w-full bg-surface-container-lowest rounded-full overflow-hidden">
                    <div className="h-full bg-primary w-[99%]"></div>
                  </div>
                </div>
              </div>

              <div className="mt-16 w-full h-48 rounded-2xl overflow-hidden relative">
                <img
                  alt="Smart Agriculture Visualization"
                  className="w-full h-full object-cover opacity-40"
                  data-alt="A wide panoramic shot of a ultra-modern, clean livestock facility at dusk. The scene is illuminated by soft, cool-toned clinical LEDs and the glow of holographic interfaces. Healthy cattle are visible in organized, spacious stalls while digital data streams and wireframe overlays represent health tracking and AI diagnostics. The visual style is cinematic and high-tech, using a deep navy and emerald green color palette."
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
        </div>
      </main>
    </div>
  )
}
