export default function WellnessDashboard() {
  return (
    <div className="antialiased selection:bg-primary/30 bg-background text-on-surface">
      <aside className="h-screen w-64 fixed left-0 top-0 bg-[#131b2e] border-r border-emerald-500/10 flex flex-col py-6 tracking-tight z-50">
        <div className="px-6 mb-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-500 rounded flex items-center justify-center">
              <span
                className="material-symbols-outlined text-white text-xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                shield
              </span>
            </div>
            <div>
              <h1 className="text-white font-bold tracking-tight leading-none text-base uppercase">
                ADRS CORE
              </h1>
              <p className="text-[10px] uppercase tracking-widest text-emerald-500/60 mt-0.5">
                Clinical Precision
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
            <span className="material-symbols-outlined text-[20px]">health_and_safety</span>
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
            <span className="material-symbols-outlined text-[20px]">partly_cloudy_day</span>
            <span className="text-sm">Seasonal Forecasting</span>
          </a>
        </nav>

        <div className="px-4 pb-6 mt-auto">
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

      <main className="ml-64 min-h-screen flex flex-col">
        <header className="sticky top-0 z-40 bg-[#0b1326]/80 backdrop-blur-xl border-b border-white/5 flex justify-between items-center h-16 px-8 font-medium text-sm">
          <div className="flex items-center gap-6 flex-1">
            <div className="relative w-full max-w-md group">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg group-focus-within:text-emerald-500 transition-colors">
                search
              </span>
              <input
                className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all placeholder:text-slate-500"
                placeholder="Search livestock ID or wellness reports..."
                type="text"
              />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button className="w-10 h-10 flex items-center justify-center text-slate-400 hover:text-emerald-300 transition-colors relative">
              <span className="material-symbols-outlined">notifications</span>
              <span className="absolute top-2 right-2 w-2 h-2 bg-emerald-500 rounded-full border-2 border-[#0b1326]"></span>
            </button>
            <button className="w-10 h-10 flex items-center justify-center text-slate-400 hover:text-emerald-300 transition-colors">
              <span className="material-symbols-outlined">settings</span>
            </button>
            <div className="h-6 w-px bg-white/10 mx-2"></div>
            <div className="flex items-center gap-3 pl-2 border-l border-white/10">
              <div className="text-right hidden sm:block">
                <p className="text-xs font-bold text-on-surface">Kamal Perera</p>
                <p className="text-[10px] text-slate-500">Dairy Farmer</p>
              </div>
              <div className="w-8 h-8 rounded-full bg-surface-container-highest overflow-hidden border border-emerald-500/20">
                <img
                  alt="User profile"
                  className="w-full h-full object-cover"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuAzZ15WNVDFyCeC9Q3qTqV9lyRW0nla5u5Jz521YpAqcWp8an1GRRSi2QTuY0whhQjJcZ77Zd6met8Q45dl7_9_6pc6IL-9kONKWf4CbdgoNnBCxm02CYZ2uL56R6_T6RTt8c3-jpOffYcb_tjqO8BXenfopVMbmbXm1RMeA8Gk4IGWmn2K99li1kDj-wOYPyQaea_IXPvhExE0SPjl7MhO7tkHMY8yyESjAltyTREMe-BoOC5PRNGwmK6E1gVxwJed1PTfHsL6_nii"
                />
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs font-bold text-on-surface tracking-tight">Wellness &amp; BCS</p>
              <p className="text-[10px] text-emerald-500 uppercase font-black">Live Stream</p>
            </div>
          </div>
        </header>

        <div className="p-8 max-w-7xl mx-auto w-full space-y-8">
          <div className="flex flex-col gap-1">
            <h2 className="text-3xl font-extrabold tracking-tight text-on-surface">
              Herd Wellness Dashboard
            </h2>
            <p className="text-slate-400">
              Real-time biosecurity surveillance and Body Condition Scoring (BCS) analytics.
            </p>
          </div>

          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-5 glass-panel rounded-xl p-6 flex flex-col justify-between relative overflow-hidden">
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

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <button className="group relative overflow-hidden bg-surface-container-high rounded-xl p-8 flex flex-col text-left transition-all duration-300 hover:scale-[1.01] hover:shadow-2xl hover:shadow-primary/10">
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
            </button>

            <button className="group relative overflow-hidden bg-surface-container-high rounded-xl p-8 flex flex-col text-left transition-all duration-300 hover:scale-[1.01] hover:shadow-2xl hover:shadow-primary/10">
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
            </button>
          </div>

          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-8 bg-surface-container rounded-xl overflow-hidden border border-white/5">
              <div className="p-6 border-b border-white/5 flex justify-between items-center">
                <h3 className="text-lg font-bold">Recent BCS Assessments</h3>
                <button className="text-primary text-xs font-bold uppercase tracking-widest hover:underline">
                  View History
                </button>
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
                        <button className="material-symbols-outlined text-slate-400 hover:text-primary transition-colors">
                          more_horiz
                        </button>
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
                        <button className="material-symbols-outlined text-slate-400 hover:text-primary transition-colors">
                          more_horiz
                        </button>
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
                  data-alt="A high-angle professional drone shot of healthy cattle grazing in a lush, green pasture during the golden hour. The image is overlaid with a digital holographic grid and thermal heat map markers indicating individual health metrics. The lighting is cinematic with long shadows and a crisp, high-tech clarity, blending organic nature with advanced clinical surveillance technology."
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
      </main>
    </div>
  )
}
