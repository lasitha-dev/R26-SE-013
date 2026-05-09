export default function SettingsFarmConfiguration() {
  return (
    <div className="bg-surface text-on-surface selection:bg-primary/30 min-h-screen flex">
      <aside className="fixed left-0 h-screen w-72 bg-surface-container-low shadow-[10px_0_30px_rgba(0,0,0,0.3)] flex flex-col justify-between py-8 px-4 z-50">
        <div>
          <div className="mb-12 px-4">
            <div className="flex items-center gap-3">
              <span
                className="material-symbols-outlined text-primary text-3xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                shield
              </span>
              <div>
                <h1 className="text-primary font-black tracking-tighter text-lg leading-none">ADRS CORE</h1>
                <p className="text-[0.6rem] text-primary/60 tracking-[0.2em] font-bold mt-1">CLINICAL PRECISION</p>
              </div>
            </div>
          </div>
          <nav className="space-y-1">
            {[
              { icon: 'pets', label: 'Herd Registry' },
              { icon: 'health_and_safety', label: 'Wellness & BCS' },
              { icon: 'psychology', label: 'AI Smart Diagnosis' },
              { icon: 'public', label: 'Geospatial Intelligence' },
              { icon: 'wb_sunny', label: 'Seasonal Forecasting' },
            ].map((item) => (
              <a
                key={item.label}
                className="flex items-center gap-4 py-3 px-4 rounded-lg text-slate-400 hover:text-slate-200 opacity-80 hover:bg-surface-container-high transition-all duration-300 group"
                href="#"
              >
                <span className="material-symbols-outlined group-hover:text-primary">{item.icon}</span>
                <span className="font-medium tracking-wide text-sm">{item.label}</span>
              </a>
            ))}
          </nav>
        </div>

        <div className="space-y-1">
          <a
            className="flex items-center gap-4 py-3 px-4 rounded-lg text-primary bg-surface-container border-r-2 border-primary transition-all duration-300 scale-[0.98]"
            href="#"
          >
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
              settings
            </span>
            <span className="font-medium tracking-wide text-sm">Settings</span>
          </a>
          <a
            className="flex items-center gap-4 py-3 px-4 rounded-lg text-slate-400 hover:text-slate-200 opacity-80 hover:bg-surface-container-high transition-all duration-300 group"
            href="#"
          >
            <span className="material-symbols-outlined group-hover:text-primary">help</span>
            <span className="font-medium tracking-wide text-sm">Support</span>
          </a>
        </div>
      </aside>

      <main className="flex-1 ml-72 flex flex-col min-h-screen">
        <header className="sticky top-0 w-full bg-surface/80 backdrop-blur-xl flex justify-between items-center px-12 py-6 z-40">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-primary animate-pulse"></span>
            <span className="text-[0.65rem] tracking-[0.3em] font-black text-primary/60 uppercase">System Active</span>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="text-sm font-bold text-on-surface">Kamal Perera</p>
              <p className="text-[0.7rem] text-on-surface-variant font-medium">Dairy Farmer</p>
            </div>
            <div className="relative group">
              <img
                alt="Kamal Perera farmer profile"
                className="w-12 h-12 rounded-full object-cover border-2 border-surface-container-highest group-hover:border-primary transition-all duration-300"
                data-alt="A professional portrait of a senior agricultural manager with a warm smile, wearing a technical outdoor vest. The background is a softly blurred modern office with agricultural telemetry charts on a screen. The lighting is crisp and clinical, emphasizing reliability and technological expertise in a modern farming environment."
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuAP1aMX4_EQOOv36urUvMemnEFDUBe-oqi-iN_IYyTbEaVxdbsd5z0iVBod39t8eqGzc-X8VV_3kv99LsB9gX-opna2_-Lc4B1QM4Bn90FQCj9XeyYiy3I1JOlBQff2NtW3EAPFP9BoAK1gLE6ojuGZir9PHBT3jEtHpjFRkqaN7shlffXKKXKAyelC0f0Cer3L_1ugaGN_sUaykqN1GOuARGW9jK7q7Oz-8BDNEQSJXcz553DEGbcLKGsE8L0CubbQeL2fiZ6WOROC"
              />
            </div>
          </div>
        </header>

        <section className="flex-1 px-12 py-8 max-w-6xl mx-auto w-full">
          <div className="mb-12">
            <h2 className="text-4xl font-extrabold tracking-tight text-on-surface mb-2">
              SYSTEM CONFIGURATION <span className="text-primary">&amp;</span> SETTINGS
            </h2>
            <div className="h-1 w-24 bg-primary rounded-full"></div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-24">
            <div className="bg-surface-container p-8 rounded-xl shadow-2xl relative overflow-hidden group">
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

            <div className="bg-surface-container p-8 rounded-xl shadow-2xl relative overflow-hidden group">
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

            <div className="md:col-span-2 bg-surface-container-high p-8 rounded-xl shadow-2xl border-l-4 border-primary/20">
              <h3 className="text-lg font-bold text-primary mb-8 flex items-center gap-2">
                <span className="material-symbols-outlined text-base">security</span>
                Data &amp; Security
              </h3>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-center">
                <div className="space-y-4">
                  <button
                    className="w-full flex items-center justify-center gap-3 bg-surface-container-highest hover:bg-surface-variant text-primary font-bold py-4 px-6 rounded-lg transition-all active:scale-95"
                    type="button"
                  >
                    <span className="material-symbols-outlined">download</span>
                    Export Farm Data (CSV)
                  </button>
                  <button
                    className="w-full flex items-center justify-center gap-3 bg-surface-container-highest hover:bg-surface-variant text-primary font-bold py-4 px-6 rounded-lg transition-all active:scale-95"
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
        </section>

        <div className="fixed bottom-10 right-10 z-50">
          <button
            className="flex items-center gap-3 bg-gradient-to-br from-primary to-primary-container text-on-primary-container px-8 py-4 rounded-full font-black text-sm tracking-widest uppercase shadow-[0_10px_40px_rgba(16,185,129,0.3)] hover:shadow-[0_15px_50px_rgba(16,185,129,0.5)] hover:-translate-y-1 transition-all active:scale-95"
            type="button"
          >
            <span className="material-symbols-outlined">save</span>
            Save Configurations
          </button>
        </div>
      </main>

      <div
        className="fixed inset-0 pointer-events-none opacity-[0.03] mix-blend-overlay z-[60]"
        style={{
          backgroundImage:
            "url('https://lh3.googleusercontent.com/aida-public/AB6AXuCPt9HG1bxW49C5nab1tyBcceh937NDnI1OyoGabCJsHgm7Mw8zLXJ2lmXrUXgZQLZBn9C9uUzTXIe5KZa_X-wojzu4L5_8V9lnTdisLqRZ_G9CCrqvTuKw-WnygqY5juhBuJrHOCb0UOGR4I6M0cLiQ96lfDpLmFYWH4OYAubX6BzceXOioL4p5Kx0NBGX-y_b6I_A-1638izAFm6kvwUa4w6Z33x_idzqHZMhpKG8GWHWB0L7dV8CyeoDxaYPeidqFFU83FAV0ahP')",
        }}
      ></div>
    </div>
  )
}
