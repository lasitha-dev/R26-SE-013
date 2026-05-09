export default function SevenDayTriageScan() {
  return (
    <div className="bg-surface text-on-surface selection:bg-primary-container selection:text-on-primary-container overflow-hidden h-screen flex">
      <aside className="bg-[#131b2e] flex flex-col h-full p-4 space-y-6 w-72 flex-shrink-0">
        <div className="flex items-center gap-3 px-2">
          <div className="w-10 h-10 bg-[#10b981] rounded flex items-center justify-center">
            <span
              className="material-symbols-outlined text-white"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              shield
            </span>
          </div>
          <div>
            <h1 className="text-lg font-black text-white uppercase tracking-wider">ADRS Core</h1>
            <p className="text-[10px] text-tertiary uppercase tracking-[0.2em] opacity-60">
              Clinical Precision
            </p>
          </div>
        </div>

        <nav className="flex-1 space-y-1">
          <a
            className="flex items-center gap-3 px-4 py-3 text-[#bcc7de] opacity-70 hover:opacity-100 hover:bg-[#171f33] rounded-lg font-medium text-sm transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined">pets</span>Herd Registry
          </a>
          <a
            className="flex items-center gap-3 px-4 py-3 bg-[#222a3d] text-[#4edea3] rounded-lg shadow-[0_0_15px_rgba(78,222,163,0.1)] font-medium text-sm transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined">health_and_safety</span>Wellness &amp; BCS
          </a>
          <a
            className="flex items-center gap-3 px-4 py-3 text-[#bcc7de] opacity-70 hover:opacity-100 hover:bg-[#171f33] rounded-lg font-medium text-sm transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined">memory</span>AI Smart Diagnosis
          </a>
          <a
            className="flex items-center gap-3 px-4 py-3 text-[#bcc7de] opacity-70 hover:opacity-100 hover:bg-[#171f33] rounded-lg font-medium text-sm transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined">map</span>Geospatial Intelligence
          </a>
          <a
            className="flex items-center gap-3 px-4 py-3 text-[#bcc7de] opacity-70 hover:opacity-100 hover:bg-[#171f33] rounded-lg font-medium text-sm transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined">partly_cloudy_day</span>Seasonal Forecasting
          </a>
        </nav>

        <div className="space-y-1">
          <a
            className="flex items-center gap-3 px-4 py-2 text-[#bcc7de] opacity-70 hover:opacity-100 font-medium text-sm"
            href="#"
          >
            <span className="material-symbols-outlined">settings</span>Settings
          </a>
          <a
            className="flex items-center gap-3 px-4 py-2 text-[#bcc7de] opacity-70 hover:opacity-100 font-medium text-sm"
            href="#"
          >
            <span className="material-symbols-outlined">help</span>Support
          </a>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <header className="bg-[#0b1326] flex justify-between items-center w-full px-8 py-3 h-16 sticky top-0 z-10">
          <div className="flex items-center gap-4 flex-1">
            <div className="relative w-full max-w-md">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-tertiary text-lg">
                search
              </span>
              <input
                className="bg-[#131b2e] border-none rounded-full py-2 pl-10 pr-4 w-full text-sm text-on-surface focus:ring-1 focus:ring-primary placeholder:text-tertiary/40"
                placeholder="Search case ID, animal profile..."
                type="text"
              />
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex gap-4">
              <button className="text-[#bcc7de] opacity-80 hover:text-[#4edea3] transition-colors relative">
                <span className="material-symbols-outlined">notifications</span>
                <span className="absolute top-0 right-0 w-2 h-2 bg-error rounded-full"></span>
              </button>
              <button className="text-slate-300 hover:bg-[#171f33] p-2 rounded-full transition-opacity active:opacity-80">
                <span className="material-symbols-outlined">apps</span>
              </button>
            </div>
            <div className="h-8 w-px bg-outline-variant/20"></div>
            <div className="flex items-center gap-3 group cursor-pointer">
              <div className="text-right">
                <p className="text-sm font-bold text-on-surface">Kamal Perera</p>
                <p className="text-[10px] text-tertiary uppercase tracking-wider font-semibold opacity-60">
                  Dairy Farmer
                </p>
              </div>
              <img
                alt="Chief Veterinarian Profile"
                className="w-10 h-10 rounded-full border-2 border-primary/20 object-cover group-hover:border-primary transition-all"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDoA7xd4wmMY8uDMSs92VmSSj2hm3zQaG5V5DE3D2rTMRaF25xcbIxJ70Ea187chIZIgZfLcCpGsHQXEYd-fO4SyNkmwDARVyHimxtvDWG2NTQ1NzHto59AjhF0EKW2lAvGJ8HWDhGwAh2uvOdzifZrS-HIe3vnn1TB9aHy2igJP1rryddkoPOeUAEce3FLRbfWRI8QV4D5R8KLQtKD53KbJ3YInjtMyPzSzePVvbNpmSFbhErUilPyJR3yUZcwvNELtzaQHOn5z-NR"
              />
            </div>
          </div>
        </header>

        <section className="p-8 space-y-6 flex-1">
          <div className="flex flex-col gap-1">
            <p className="text-primary text-xs font-black tracking-[0.3em] uppercase opacity-80">
              Phase 01: Diagnostics
            </p>
            <h2 className="text-4xl font-black text-[#4edea3] tracking-tighter uppercase font-headline">
              7-Day Wellness Triage Intake
            </h2>
            <div className="h-1 w-24 bg-gradient-to-r from-primary to-transparent mt-2"></div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-4 h-full">
              <div className="glass-card rounded-xl p-8 flex flex-col items-center justify-center text-center group cursor-pointer border-dashed border-2 border-primary/20 hover:border-primary/50 transition-all h-full min-h-[400px] relative overflow-hidden">
                <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <div className="w-20 h-20 rounded-full bg-surface-container-highest flex items-center justify-center mb-6 ring-8 ring-surface-container-low">
                  <span className="material-symbols-outlined text-4xl text-primary">photo_camera</span>
                </div>
                <h3 className="text-xl font-bold text-on-surface mb-2">Upload Top-Down Cattle Image</h3>
                <p className="text-tertiary text-sm leading-relaxed max-w-[240px]">
                  Instructions: Capture a top-down (dorsal) view directly above the animal. Ensure the spine (backbone), hooks, and pins are clearly visible for accurate AI Body Condition Scoring.
                </p>
                <div className="mt-8">
                  <span className="px-3 py-1 bg-surface-container-lowest text-[10px] font-bold text-primary rounded border border-primary/20 uppercase tracking-widest">
                    AI Ready
                  </span>
                </div>
                <img
                  alt="Cattle sample silhouette"
                  className="absolute inset-0 w-full h-full object-cover opacity-5 grayscale pointer-events-none"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuD94UGqSbH7XnaRa0bul0RmiEpvD1U8WGQCr51XEjxrXJ5HjpQdXthgwGFgwuJCcDNompGgStodu-_9ZWm2yToCTex1rLwTIpogHGrcM12juFwP6yuo7MOmVGxdnJ5dg-kGlQg4XqxvEuKxdcXMkmLvLYIdzNbLeKPdb7A0ZNG9XeU2c8pwImbU4WnntG-USsYtvl5vX4YxVvRCLX555eP2NhqFn286aWvtdgHgFqk-qyqj_pNomYpUnW8gMV3EfOOM2Xtt5q4aHGBC"
                />
              </div>
            </div>

            <div className="lg:col-span-8">
              <div className="glass-card rounded-xl p-6 h-full flex flex-col">
                <div className="flex items-center gap-3 mb-6">
                  <span className="material-symbols-outlined text-secondary">clinical_notes</span>
                  <h3 className="text-lg font-bold text-on-surface tracking-tight uppercase">
                    7-Day Physiological Logs
                  </h3>
                </div>
                <div className="flex-1 overflow-x-auto">
                  <table className="w-full text-left border-separate border-spacing-2">
                    <thead>
                      <tr>
                        <th className="p-2 text-[10px] font-black text-tertiary uppercase tracking-widest text-left w-32">
                          Metric
                        </th>
                        {['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'].map((d) => (
                          <th
                            key={d}
                            className="p-2 text-[10px] font-black text-primary uppercase tracking-widest text-center whitespace-nowrap"
                          >
                            {d}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="p-2 align-middle">
                          <p className="text-xs font-bold text-on-surface">Water Intake</p>
                          <p className="text-[9px] text-tertiary/60 font-medium">Liters / Day</p>
                        </td>
                        {[65, 68, 62, 70, 66, 72, 68].map((v, idx) => (
                          <td key={idx} className="p-1">
                            <input
                              className="w-full bg-[#060e20] border-none rounded py-2 text-center text-sm font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1"
                              placeholder="0"
                              type="number"
                              defaultValue={v}
                            />
                          </td>
                        ))}
                      </tr>

                      <tr>
                        <td className="p-2 align-middle">
                          <p className="text-xs font-bold text-on-surface">Feed Intake</p>
                          <p className="text-[9px] text-tertiary/60 font-medium">KG / Day</p>
                        </td>
                        {[14.2, 14.5, 13.8, 14.0, 14.1, 14.3, 14.2].map((v, idx) => (
                          <td key={idx} className="p-1">
                            <input
                              className="w-full bg-[#060e20] border-none rounded py-2 text-center text-sm font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1"
                              placeholder="0"
                              type="number"
                              defaultValue={v}
                            />
                          </td>
                        ))}
                      </tr>

                      <tr>
                        <td className="p-2 align-middle">
                          <p className="text-xs font-bold text-on-surface">Milk Yield</p>
                          <p className="text-[9px] text-tertiary/60 font-medium">Liters / Day</p>
                        </td>
                        {[28, 27, 29, 28, 26, 28, 30].map((v, idx) => (
                          <td key={idx} className="p-1">
                            <input
                              className="w-full bg-[#060e20] border-none rounded py-2 text-center text-sm font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1"
                              placeholder="0"
                              type="number"
                              defaultValue={v}
                            />
                          </td>
                        ))}
                      </tr>

                      <tr>
                        <td className="p-2 align-middle">
                          <p className="text-xs font-bold text-on-surface">Body Temp</p>
                          <p className="text-[9px] text-tertiary/60 font-medium">Celsius (°C)</p>
                        </td>
                        {[38.5, 38.6, 38.4, 38.5, 38.7, 38.5, 38.5].map((v, idx) => (
                          <td key={idx} className="p-1">
                            <input
                              className="w-full bg-[#060e20] border-none rounded py-2 text-center text-sm font-bold text-primary focus:ring-1 focus:ring-primary shadow-inner px-1"
                              placeholder="0"
                              type="number"
                              defaultValue={v}
                            />
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          <div className="w-full">
            <div className="bg-[#171f33] rounded-xl p-5 border-l-4 border-secondary flex flex-col md:flex-row items-center justify-between gap-6 relative overflow-hidden">
              <div className="flex items-center gap-4 relative z-10">
                <div className="w-10 h-10 rounded-full bg-secondary/10 flex items-center justify-center">
                  <span className="material-symbols-outlined text-secondary animate-pulse">radar</span>
                </div>
                <div>
                  <h4 className="text-[10px] font-black text-secondary tracking-widest uppercase">
                    Live GPS Synced
                  </h4>
                  <p className="text-on-surface text-sm font-medium">
                    Fetching local THI (Ambient Temp &amp; Humidity)...
                  </p>
                </div>
              </div>
              <div className="flex gap-8 relative z-10">
                <div className="text-center">
                  <p className="text-[9px] font-black text-tertiary uppercase">Ambient Temp</p>
                  <p className="text-lg font-bold text-on-surface">31.4°C</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] font-black text-tertiary uppercase">Humidity</p>
                  <p className="text-lg font-bold text-on-surface">78%</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] font-black text-secondary uppercase">Calculated THI</p>
                  <p className="text-lg font-black text-secondary">
                    82.4 <span className="text-[9px] font-normal text-error ml-1">[STRESS]</span>
                  </p>
                </div>
              </div>
              <div className="absolute right-0 top-0 h-full w-48 opacity-10">
                <img
                  alt="Map background"
                  className="h-full w-full object-cover"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuC5dvK_WKT77odUdmwrY5QnXxX8YKiB9-IAuUM3xR3KRGN0UHrEFXA0DNCT8G6LJxNXxIv-GUfmReDRVuyoYjDUlW12BSjSESkic-aQ9K1giY3O_KRwRYmw8u7cqAh_Lh6bfkkvepFac5xxjZvsQbrSGjywfRbL-puE_hzEx_cBypeLJTYvH9cSQL545nKpzmGLFCtnxbizlFpYESu68aI5JCUvWK1k3_xgVzKjwg6Y6cxfc3dL1S-mfgFXmNTbY9zyhSgiObXXJcR8"
                />
              </div>
            </div>
          </div>

          <div className="pt-4">
            <button className="group relative overflow-hidden bg-primary rounded-xl p-6 w-full flex items-center justify-center text-on-primary transition-all duration-300 hover:scale-[1.01] hover:shadow-2xl hover:shadow-primary/20">
              <div className="absolute inset-0 bg-gradient-to-r from-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
              <div className="flex items-center gap-4 relative z-10">
                <span
                  className="material-symbols-outlined text-3xl"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  bolt
                </span>
                <span className="text-xl font-bold uppercase tracking-widest">
                  Run Multi-Modal AI Diagnostics
                </span>
                <span className="material-symbols-outlined text-3xl group-hover:translate-x-2 transition-transform">
                  arrow_forward
                </span>
              </div>
            </button>
          </div>
        </section>
      </main>
    </div>
  )
}
