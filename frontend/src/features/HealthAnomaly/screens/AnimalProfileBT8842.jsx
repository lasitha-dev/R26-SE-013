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
    <div className="font-body antialiased bg-surface text-on-surface min-h-screen">
      <aside className="h-screen w-64 fixed left-0 top-0 bg-surface-container-low flex flex-col py-8 px-4 tracking-tight z-50">
        <div className="mb-10 px-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-container rounded flex items-center justify-center">
              <span
                className="material-symbols-outlined text-white"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                shield
              </span>
            </div>
            <div>
              <div className="text-lg font-black tracking-widest text-primary">ADRS CORE</div>
              <div className="text-[10px] font-bold text-slate-500 tracking-[0.2em]">CLINICAL PRECISION</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-2">
          <a
            className="flex items-center gap-3 py-3 px-4 text-primary font-bold bg-surface-container-high rounded-lg shadow-[0_0_15px_rgba(16,185,129,0.1)] active:scale-[0.98] transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined">pets</span>
            <span className="text-sm">Herd Registry</span>
          </a>
          {[
            { icon: 'health_and_safety', label: 'Wellness & BCS' },
            { icon: 'psychology', label: 'AI Smart Diagnosis' },
            { icon: 'map', label: 'Geospatial Intelligence' },
            { icon: 'wb_sunny', label: 'Seasonal Forecasting' },
          ].map((item) => (
            <a
              key={item.label}
              className="flex items-center gap-3 py-3 px-4 text-slate-400/80 hover:text-primary-fixed hover:bg-surface-container transition-colors active:scale-[0.98]"
              href="#"
            >
              <span className="material-symbols-outlined">{item.icon}</span>
              <span className="text-sm">{item.label}</span>
            </a>
          ))}
        </nav>

        <div className="mt-auto pt-6 border-t border-slate-800/50">
          <div className="space-y-1">
            {[
              { icon: 'settings', label: 'Settings' },
              { icon: 'contact_support', label: 'Support' },
            ].map((item) => (
              <a
                key={item.label}
                className="flex items-center gap-3 py-2 px-4 text-slate-400/80 hover:text-primary-fixed transition-colors"
                href="#"
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                <span className="text-sm">{item.label}</span>
              </a>
            ))}
          </div>
        </div>
      </aside>

      <header className="fixed top-0 right-0 w-[calc(100%-16rem)] z-40 bg-surface/80 backdrop-blur-xl flex justify-between items-center h-16 px-8 ml-64 text-sm font-medium">
        <div className="text-base font-bold text-slate-100 uppercase tracking-wide">Kamal Perera - Dairy Farmer</div>
        <div className="flex items-center gap-6 text-primary">
          <button
            className="relative cursor-pointer hover:text-primary-fixed transition-colors active:opacity-80"
            type="button"
          >
            <span className="material-symbols-outlined">notifications</span>
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-error rounded-full"></span>
          </button>
          <button className="flex items-center gap-3 cursor-pointer hover:text-primary-fixed transition-colors active:opacity-80" type="button">
            <img
              className="w-8 h-8 rounded-full object-cover"
              data-alt="A professional headshot of a middle-aged South Asian man with a warm, expert expression, wearing a clean linen shirt. The portrait is captured with high-end studio lighting that creates soft shadows and a shallow depth of field, with a muted architectural background in deep blues and grays that perfectly complements the clinical dashboard aesthetic."
              alt="Profile"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAVLLBURH_1s36s4fwcqRnAm3O33DUTut83TY6zbq-MDJcayjESHszMK7dt0YbPQGe-gFXI98fgIYdpyMGgjVRZKxUsMzJk9andFGQLcCAWBflBg8jZtrN6xwq4ZP5pQq1hsI69gByMROGIzxVKikyH_KUzxRepw_udRcAxcLPw4cgfzO3oOq7tzjxBdxYt8lvVpIhJKbAKh8osiKhHehui2X-BKpXkJa-GBfdRpH4G22rLf6p-FAoQgoZ1eEkUF_lNLwFVVgcnRbwT"
            />
            <span className="material-symbols-outlined">account_circle</span>
          </button>
        </div>
      </header>

      <main className="ml-64 mt-16 p-8 min-h-screen bg-surface">
        <div className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-primary-fixed uppercase text-[10px] font-black tracking-[0.3em]">
                Precision Monitoring
              </span>
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
          <div className="col-span-12 lg:col-span-5 bg-surface-container-low rounded-lg overflow-hidden border border-outline-variant/10">
            <div className="relative h-64">
              <img
                className="w-full h-full object-cover"
                data-alt="A cinematic, high-resolution close-up portrait of a healthy black and white Friesian cow in a clean, modern dairy facility. The lighting is soft and clinical, highlighting the texture of the coat and the brightness of the eyes. The background consists of out-of-focus architectural elements of the farm in deep navy and silver tones, creating a professional, veterinary-grade atmospheric aesthetic."
                alt="Animal"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCiDHwgu_S_VlRp-pHNwe1pZ1kdfjH7-cjRjnTmY3WgNkIviJaMiUZwZPiz5nMWnshpsGdABZOfkBFDR5bEuY3K6dCitqigCsXRYZCpLbfvqaIiGjNG_6Xl22nv4Q9Wt9ZFvAx8_jsCq0rYyzedHopCF1sVpXufe6Q3jbmfy9-F_oAVD6OZtFZi-JpREOdOdA8D-Ya8P_YlZZzFpAHdJtStvpViZvfdz7l0BkNxllL_18QVkJ5-c1AkcoXR_ZWVcvDrst-FAUiia32J"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-surface-container-low via-transparent to-transparent"></div>
              <div className="absolute bottom-4 left-6">
                <p className="text-[10px] font-bold text-primary tracking-widest uppercase">Registration ID</p>
                <p className="text-xl font-bold text-white">LK-C-4421-8842</p>
              </div>
            </div>
            <div className="p-8 space-y-6">
              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: 'Current Weight', value: '450', unit: 'KG' },
                  { label: 'Lactation Phase', value: 'Mid' },
                  { label: 'Avg Daily Yield', value: '28', unit: 'L' },
                ].map((m) => (
                  <div key={m.label}>
                    <p className="text-[10px] font-bold text-slate-500 tracking-widest uppercase mb-1">{m.label}</p>
                    <p className="text-2xl font-black text-on-surface tracking-tight">
                      {m.value}
                      {m.unit ? <span className="text-xs font-medium text-slate-400"> {m.unit}</span> : null}
                    </p>
                  </div>
                ))}
              </div>
              <div className="pt-6 border-t border-outline-variant/10">
                <h4 className="text-[10px] font-black text-primary tracking-[0.2em] uppercase mb-4">Genetic Profile</h4>
                <div className="space-y-3">
                  {[
                    { k: 'Dam ID', v: '#BT-7721', mono: true },
                    { k: 'Sire ID', v: '#BT-9012', mono: true },
                    { k: 'Birth Date', v: 'Oct 12, 2019' },
                  ].map((r) => (
                    <div key={r.k} className="flex justify-between items-center text-xs">
                      <span className="text-slate-400">{r.k}</span>
                      <span className={r.mono ? 'font-mono text-white' : 'text-white'}>{r.v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-12 lg:col-span-7 space-y-6">
            <div className="bg-surface-container rounded-lg p-8 border border-outline-variant/10">
              <div className="flex justify-between items-start mb-8">
                <div>
                  <h3 className="text-xs font-black text-white tracking-[0.2em] uppercase">30-Day Milk Yield Trend</h3>
                  <p className="text-[11px] text-slate-400 mt-1">Daily production variance in Liters</p>
                </div>
                <div className="text-right">
                  <p className="text-xl font-black text-primary">+4.2%</p>
                  <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Monthly Growth</p>
                </div>
              </div>
              <div className="relative h-32 flex items-end gap-1">
                {yieldBars.map((bar, idx) => (
                  <div
                    key={idx}
                    className={`flex-1 rounded-t ${bar.cls} ${bar.h} ${bar.topBorder ? 'border-t-2 border-primary' : ''}`}
                  ></div>
                ))}
              </div>
              <div className="flex justify-between mt-4 text-[10px] font-bold text-slate-600 tracking-widest uppercase">
                <span>Day 01</span>
                <span>Day 15</span>
                <span>Day 30</span>
              </div>
            </div>

            <div className="bg-surface-container rounded-lg p-8 border border-outline-variant/10">
              <div className="flex justify-between items-start mb-8">
                <div>
                  <h3 className="text-xs font-black text-white tracking-[0.2em] uppercase">BCS &amp; Weight Fluctuation</h3>
                  <p className="text-[11px] text-slate-400 mt-1">Body Condition Score tracking (1-5 scale)</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-secondary"></span>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">BCS Score</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-tertiary"></span>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Weight</span>
                  </div>
                </div>
              </div>
              <div className="h-32 relative">
                <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 400 100">
                  <path
                    d="M0,80 Q50,70 100,75 T200,60 T300,65 T400,55"
                    fill="none"
                    className="stroke-secondary"
                    strokeWidth="2"
                  ></path>
                  <path
                    d="M0,50 Q50,55 100,45 T200,50 T300,40 T400,45"
                    fill="none"
                    className="stroke-tertiary"
                    strokeDasharray="4"
                    strokeWidth="1.5"
                  ></path>
                </svg>
                <div className="absolute top-0 left-0 h-full flex flex-col justify-between text-[10px] font-bold text-slate-600">
                  <span>Optimal</span>
                  <span>Critical</span>
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-12 bg-surface-container rounded-lg overflow-hidden border border-outline-variant/10">
            <div className="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center">
              <div>
                <h3 className="text-xs font-black text-white tracking-[0.2em] uppercase">
                  Recent AI Scans &amp; Diagnostics
                </h3>
                <p className="text-[11px] text-slate-400 mt-1">History of automated screenings and expert evaluations</p>
              </div>
              <button
                className="text-primary text-[10px] font-black tracking-widest uppercase hover:underline"
                type="button"
              >
                View All History
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-container-high/30">
                    {['Date', 'Diagnostic Type', 'Result'].map((h) => (
                      <th
                        key={h}
                        className="px-8 py-4 text-[10px] font-black text-slate-500 tracking-[0.2em] uppercase"
                      >
                        {h}
                      </th>
                    ))}
                    <th className="px-8 py-4 text-[10px] font-black text-slate-500 tracking-[0.2em] uppercase text-right">
                      Actions
                    </th>
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
      </main>
    </div>
  )
}
