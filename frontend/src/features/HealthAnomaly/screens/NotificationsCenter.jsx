export default function NotificationsCenter() {
  return (
    <div className="font-body antialiased selection:bg-primary selection:text-on-primary bg-background text-on-surface">
      <div className="flex min-h-screen">
        <aside className="hidden md:flex flex-col h-screen w-72 sticky left-0 top-0 bg-[#0b1326] py-8 px-4 gap-2">
          <div className="mb-10 px-4">
            <div className="flex items-center gap-3 mb-1">
              <div className="w-10 h-10 bg-primary-container rounded-lg flex items-center justify-center">
                <span className="material-symbols-outlined text-on-primary-container">shield</span>
              </div>
              <div>
                <h1 className="text-xl font-bold text-[#4edea3] tracking-tight">ADRS Core</h1>
                <p className="uppercase tracking-[0.05em] text-[0.6875rem] font-medium text-slate-500">
                  Sentinel Diagnostics
                </p>
              </div>
            </div>
          </div>
          <nav className="flex-1 space-y-1">
            <a
              className="flex items-center gap-3 text-slate-500 hover:text-slate-200 px-4 py-3 transition-all hover:bg-[#131b2e]/50 rounded-lg group"
              href="#"
            >
              <span className="material-symbols-outlined text-xl group-hover:text-primary transition-colors">pets</span>
              <span className="uppercase tracking-[0.05em] text-[0.6875rem] font-medium">Herd Registry</span>
            </a>
            <a
              className="flex items-center gap-3 text-slate-500 hover:text-slate-200 px-4 py-3 transition-all hover:bg-[#131b2e]/50 rounded-lg group"
              href="#"
            >
              <span className="material-symbols-outlined text-xl group-hover:text-primary transition-colors">
                monitor_heart
              </span>
              <span className="uppercase tracking-[0.05em] text-[0.6875rem] font-medium">Wellness &amp; BCS</span>
            </a>
            <a
              className="flex items-center gap-3 text-slate-500 hover:text-slate-200 px-4 py-3 transition-all hover:bg-[#131b2e]/50 rounded-lg group"
              href="#"
            >
              <span className="material-symbols-outlined text-xl group-hover:text-primary transition-colors">memory</span>
              <span className="uppercase tracking-[0.05em] text-[0.6875rem] font-medium">AI Smart Diagnosis</span>
            </a>
            <a
              className="flex items-center gap-3 text-slate-500 hover:text-slate-200 px-4 py-3 transition-all hover:bg-[#131b2e]/50 rounded-lg group"
              href="#"
            >
              <span className="material-symbols-outlined text-xl group-hover:text-primary transition-colors">map</span>
              <span className="uppercase tracking-[0.05em] text-[0.6875rem] font-medium">
                Geospatial Intelligence
              </span>
            </a>
            <a
              className="flex items-center gap-3 text-slate-500 hover:text-slate-200 px-4 py-3 transition-all hover:bg-[#131b2e]/50 rounded-lg group"
              href="#"
            >
              <span className="material-symbols-outlined text-xl group-hover:text-primary transition-colors">
                partly_cloudy_day
              </span>
              <span className="uppercase tracking-[0.05em] text-[0.6875rem] font-medium">
                Seasonal Forecasting
              </span>
            </a>
          </nav>
          <div className="mt-auto space-y-1">
            <a
              className="flex items-center gap-3 text-slate-500 hover:text-slate-200 px-4 py-3 transition-all hover:bg-[#131b2e]/50 rounded-lg group"
              href="#"
            >
              <span className="material-symbols-outlined text-xl group-hover:text-primary transition-colors">settings</span>
              <span className="uppercase tracking-[0.05em] text-[0.6875rem] font-medium">Settings</span>
            </a>
            <a
              className="flex items-center gap-3 text-slate-500 hover:text-slate-200 px-4 py-3 transition-all hover:bg-[#131b2e]/50 rounded-lg group"
              href="#"
            >
              <span className="material-symbols-outlined text-xl group-hover:text-primary transition-colors">help</span>
              <span className="uppercase tracking-[0.05em] text-[0.6875rem] font-medium">Support</span>
            </a>
          </div>
        </aside>

        <main className="flex-1 flex flex-col min-h-screen bg-surface">
          <header className="flex justify-between items-center w-full px-8 py-4 sticky top-0 z-50 bg-[#131b2e] border-none antialiased tracking-tight text-sm">
            <div className="flex items-center flex-1 max-w-xl">
              <div className="relative w-full">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">
                  search
                </span>
                <input
                  className="w-full bg-surface-container-lowest border-none rounded-lg pl-10 pr-4 py-2 text-on-surface focus:ring-1 focus:ring-primary transition-all placeholder:text-slate-600"
                  placeholder="Search diagnostics, alerts, or herd ID..."
                  type="text"
                />
              </div>
            </div>
            <div className="flex items-center gap-6 ml-8">
              <button className="relative p-2 text-slate-400 hover:text-primary transition-colors">
                <span className="material-symbols-outlined">notifications</span>
                <span className="absolute top-2 right-2 w-2 h-2 bg-error rounded-full shadow-[0_0_8px_#ffb4ab]"></span>
              </button>
              <div className="flex items-center gap-3 pl-4 border-l border-outline-variant/20">
                <div className="text-right hidden sm:block">
                  <p className="text-on-surface font-semibold text-sm leading-none">Kamal Perera</p>
                  <p className="text-slate-500 text-[10px] uppercase tracking-wider mt-1">Dairy Farmer</p>
                </div>
                <img
                  alt="Kamal Perera"
                  className="w-10 h-10 rounded-full object-cover border-2 border-primary-container/30 shadow-lg"
                  data-alt="A professional headshot of a middle-aged South Asian man with a warm smile, wearing a clean, modern utility vest suitable for agricultural management. The background is a blurred, high-tech dairy facility with soft, cinematic lighting that highlights his features. The image conveys clinical precision, deep expertise, and a calm, authoritative presence in a sophisticated veterinary tech setting."
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuB9XDd62XFPlRUShfBiXJ26Ebd9ut8tiwk5WbxUE7I0FsnrP9h6RAAkSLBcWE-oYLTc2JaPm1mAEcAJmMSXo7rDUKh49pwJYsMxSA7A7G7Iy41DXbtIuVyDb4NFsh-uoTqd7_3xg9e2l3waWjhy-27BM1PQdOiV1brgfEcRdE92KsrbGYr8Ia2bA1yuoQpHqxqhRcWU1KJSGGN8AhA6TthrTNfjgy_FeX-wwKQ0mUeYR0dYEeJoAhq7-CuFL-4t2QkOw25Svdgk5sg_"
                />
              </div>
            </div>
          </header>

          <section className="p-8 max-w-5xl mx-auto w-full flex-1">
            <div className="flex justify-between items-end mb-10">
              <div>
                <h2 className="text-xs font-bold text-primary tracking-[0.2em] uppercase mb-2">
                  Diagnostic Interface
                </h2>
                <h1 className="text-4xl font-black text-on-surface tracking-tighter uppercase">
                  System Notifications &amp; AI Alerts
                </h1>
              </div>
              <button className="px-5 py-2 text-xs font-bold text-primary border border-primary/20 rounded-full hover:bg-primary/5 transition-all active:scale-95 flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">done_all</span>
                MARK ALL AS READ
              </button>
            </div>

            <div className="space-y-6">
              <div className="group relative overflow-hidden bg-surface-container-low rounded-xl transition-all hover:bg-surface-container-high">
                <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-error"></div>
                <div className="p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
                  <div className="w-14 h-14 rounded-lg bg-error-container/20 flex items-center justify-center flex-shrink-0">
                    <span className="material-symbols-outlined text-3xl text-error">warning</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="px-2 py-0.5 text-[10px] font-black bg-error/10 text-error rounded tracking-tighter uppercase">
                        Critical Alert
                      </span>
                      <span className="text-[10px] text-slate-500 font-medium">14 MINUTES AGO</span>
                    </div>
                    <h3 className="text-xl font-bold text-on-surface tracking-tight mb-2">
                      Action Required: Sudden Milk Yield Drop
                    </h3>
                    <p className="text-slate-400 text-sm leading-relaxed max-w-2xl">
                      Animal <span className="text-on-surface font-mono font-bold">#BT-8842</span> has shown a daily
                      yield drop of <span className="text-error font-bold">2.4 L</span> (Exceeds 2.0 L threshold).
                      Statistical modeling suggests potential early-stage Mastitis or metabolic distress. Immediate
                      7-Day Triage Scan recommended.
                    </p>
                  </div>
                  <div className="flex-shrink-0 pt-4 md:pt-0">
                    <button className="bg-error text-on-error px-6 py-3 rounded-lg font-bold text-sm flex items-center gap-2 hover:bg-error/90 active:scale-95 transition-all shadow-lg shadow-error/10">
                      Initiate Triage
                      <span className="material-symbols-outlined text-sm">arrow_forward</span>
                    </button>
                  </div>
                </div>
              </div>

              <div className="group relative overflow-hidden bg-surface-container-low rounded-xl transition-all hover:bg-surface-container-high">
                <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-secondary-container"></div>
                <div className="p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
                  <div className="w-14 h-14 rounded-lg bg-secondary-container/10 flex items-center justify-center flex-shrink-0">
                    <span className="material-symbols-outlined text-3xl text-secondary">device_thermostat</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="px-2 py-0.5 text-[10px] font-black bg-secondary-container/20 text-secondary rounded tracking-tighter uppercase">
                        Environmental Warning
                      </span>
                      <span className="text-[10px] text-slate-500 font-medium">2 HOURS AGO</span>
                    </div>
                    <h3 className="text-xl font-bold text-on-surface tracking-tight mb-2">
                      Environmental Stress Alert
                    </h3>
                    <p className="text-slate-400 text-sm leading-relaxed max-w-2xl">
                      Geospatial sensors indicate THI (Temperature Humidity Index) has reached{' '}
                      <span className="text-secondary font-bold">79</span> (Critical limit: 78). High probability of
                      decreased rumination and metabolic heat accumulation. Heat stress protocols recommended for
                      Sector B.
                    </p>
                  </div>
                  <div className="flex-shrink-0 pt-4 md:pt-0">
                    <button className="bg-surface-container-highest text-secondary border border-secondary/30 px-6 py-3 rounded-lg font-bold text-sm flex items-center gap-2 hover:bg-secondary/10 active:scale-95 transition-all">
                      View Heatmap
                      <span className="material-symbols-outlined text-sm">map</span>
                    </button>
                  </div>
                </div>
              </div>

              <div className="group relative overflow-hidden bg-surface-container-low rounded-xl transition-all hover:bg-surface-container-high">
                <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-primary-container"></div>
                <div className="p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
                  <div className="w-14 h-14 rounded-lg bg-primary-container/10 flex items-center justify-center flex-shrink-0">
                    <span className="material-symbols-outlined text-3xl text-primary">check_circle</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="px-2 py-0.5 text-[10px] font-black bg-primary-container/20 text-primary rounded tracking-tighter uppercase">
                        System Info
                      </span>
                      <span className="text-[10px] text-slate-500 font-medium">06:00 AM TODAY</span>
                    </div>
                    <h3 className="text-xl font-bold text-on-surface tracking-tight mb-2">System Sync Complete</h3>
                    <p className="text-slate-400 text-sm leading-relaxed max-w-2xl">
                      Daily physiological logs, genomic markers, and herd registry data successfully encrypted and backed
                      up to <span className="text-primary">Sentinel Cloud Architecture</span>. Integrity check: 100%
                      verified. Next scheduled sync: 24h.
                    </p>
                  </div>
                  <div className="flex-shrink-0 pt-4 md:pt-0">
                    <button className="text-slate-500 hover:text-primary px-4 py-2 text-xs font-bold uppercase tracking-widest transition-colors">
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="material-symbols-outlined text-primary">analytics</span>
                  <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500">Alert Efficiency</h4>
                </div>
                <p className="text-2xl font-bold text-on-surface">98.4%</p>
                <p className="text-xs text-slate-500 mt-1">Accuracy in predictive triage this month</p>
              </div>
              <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="material-symbols-outlined text-secondary">update</span>
                  <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                    Avg. Response Time
                  </h4>
                </div>
                <p className="text-2xl font-bold text-on-surface">12m 40s</p>
                <p className="text-xs text-slate-500 mt-1">From detection to clinical intervention</p>
              </div>
              <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="material-symbols-outlined text-error">monitoring</span>
                  <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500">Active Monitoring</h4>
                </div>
                <p className="text-2xl font-bold text-on-surface">1,240</p>
                <p className="text-xs text-slate-500 mt-1">Livestock units under real-time AI scan</p>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}
