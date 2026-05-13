export default function AiWellnessReport() {
  return (
    <div className="bg-surface text-on-surface selection:bg-primary selection:text-on-primary min-h-screen">
      <aside className="fixed left-0 top-0 h-screen w-72 flex flex-col py-8 px-4 bg-[#131b2e] z-50 border-none">
        <div className="mb-10 px-4">
          <div className="flex items-center gap-3 mb-2">
            <span
              className="material-symbols-outlined text-primary text-3xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              shield
            </span>
            <div>
              <h1 className="text-xl font-black tracking-tighter text-white leading-none">ADRS CORE</h1>
              <p className="text-[10px] font-bold tracking-[0.2em] text-slate-500 uppercase mt-1">
                CLINICAL PRECISION
              </p>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-2">
          <a
            className="flex items-center gap-3 py-3 px-4 text-slate-400 hover:text-[#4edea3] hover:bg-[#171f33] transition-all duration-300"
            href="#"
          >
            <span className="material-symbols-outlined">pets</span>
            <span className="text-sm tracking-tight">Herd Registry</span>
          </a>
          <a
            className="flex items-center gap-3 py-3 px-4 text-[#4edea3] font-bold bg-[#222a3d] rounded-r-full transition-all duration-300"
            href="#"
          >
            <span className="material-symbols-outlined">health_metrics</span>
            <span className="text-sm tracking-tight">Wellness &amp; BCS</span>
          </a>
          <a
            className="flex items-center gap-3 py-3 px-4 text-slate-400 hover:text-[#4edea3] hover:bg-[#171f33] transition-all duration-300"
            href="#"
          >
            <span className="material-symbols-outlined">memory</span>
            <span className="text-sm tracking-tight">AI Smart Diagnosis</span>
          </a>
          <a
            className="flex items-center gap-3 py-3 px-4 text-slate-400 hover:text-[#4edea3] hover:bg-[#171f33] transition-all duration-300"
            href="#"
          >
            <span className="material-symbols-outlined">map</span>
            <span className="text-sm tracking-tight">Geospatial Intelligence</span>
          </a>
          <a
            className="flex items-center gap-3 py-3 px-4 text-slate-400 hover:text-[#4edea3] hover:bg-[#171f33] transition-all duration-300"
            href="#"
          >
            <span className="material-symbols-outlined">partly_cloudy_day</span>
            <span className="text-sm tracking-tight">Seasonal Forecasting</span>
          </a>
        </nav>

        <div className="mt-auto px-4">
          <button className="w-full py-3 bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold rounded-lg text-sm tracking-wide shadow-lg shadow-primary/10 active:scale-95 transition-transform">
            NEW DIAGNOSTIC
          </button>
          <div className="mt-4 flex flex-col gap-3 px-1">
            <a className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors" href="#">
              <span className="material-symbols-outlined text-lg">settings</span>
              <span className="text-xs font-medium tracking-wide">Settings</span>
            </a>
            <a className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors" href="#">
              <span className="material-symbols-outlined text-lg">help</span>
              <span className="text-xs font-medium tracking-wide">Support</span>
            </a>
          </div>
        </div>
      </aside>

      <header className="fixed top-0 left-72 right-0 h-16 bg-[#0b1326]/80 backdrop-blur-xl z-40 flex items-center justify-between px-8 border-none">
        <div className="flex items-center bg-surface-container rounded-full px-4 py-1.5 focus-within:ring-1 focus-within:ring-[#10b981]/20 transition-all">
          <span className="material-symbols-outlined text-slate-400 text-xl">search</span>
          <input
            className="bg-transparent border-none focus:ring-0 text-sm text-on-surface placeholder:text-slate-500 w-64"
            placeholder="Search parameters..."
            type="text"
          />
        </div>
        <div className="flex items-center gap-6">
          <div className="relative">
            <span className="material-symbols-outlined text-slate-400 cursor-pointer hover:text-white transition-colors">
              notifications
            </span>
            <span className="absolute top-0 right-0 w-2 h-2 bg-error rounded-full border border-surface"></span>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-xs font-bold text-white leading-none">Kamal Perera</p>
              <p className="text-[10px] text-slate-400 uppercase tracking-tighter mt-1">Dairy Farmer</p>
            </div>
            <img
              alt="Kamal Perera Profile"
              className="w-10 h-10 rounded-full object-cover border-2 border-surface-container-high"
              data-alt="A professional close-up portrait of a South Asian man in his mid-40s with a kind expression and neat hair. He is wearing a clean, modern utility vest suitable for agricultural management. The background is a soft-focus laboratory or control center with cool blue and emerald green ambient lighting. The overall visual style is sharp, clean, and highly sophisticated, reflecting a modern dairy management environment."
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuDZF8mVpbD44AHi9FM07rmlcFkPpMAFUyOVWcLNDPNSahltG4dsdlfZ-ZGqduPFwRFgSxqcF7iVSX6qiBFxt9cRROr26JejY714CvkMjivDVMso7tTHNCwwycUmrGvirWWJhxNjZc0vmhNsf73cXr05JKJ69S2kU-MH0f1k_bzx6VURNFEb3LgrGNqV1Py0rWDAp-SENJCLEwmGi-vvo84a1ok02t-IR915HoCj7Jz8raNBc5yf70F20Ozcl8tCNNel78mg7mDq1MNO"
            />
          </div>
        </div>
      </header>

      <main className="ml-72 mt-16 p-8 min-h-screen">
        <header className="mb-8">
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-block w-2 h-2 bg-primary rounded-full animate-pulse"></span>
            <span className="text-[10px] font-bold tracking-[0.2em] text-primary uppercase">
              Active Session: Animal ID-8842
            </span>
          </div>
          <h2 className="text-4xl font-extrabold tracking-tighter text-white mb-2">
            DIAGNOSTIC TRIAGE RESULTS
          </h2>
          <div className="h-1 w-24 bg-gradient-to-r from-primary to-transparent rounded-full"></div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8">
          <section className="lg:col-span-7 bg-surface-container-low rounded-xl overflow-hidden p-1 shadow-2xl relative">
            <div className="absolute top-6 left-6 z-10 bg-surface-container-highest/60 backdrop-blur-md px-3 py-1.5 rounded-full flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-sm">visibility</span>
              <span className="text-[10px] font-bold tracking-wider text-white uppercase">
                XAI Feature Extraction map
              </span>
            </div>
            <div className="aspect-[16/10] bg-surface-container-lowest rounded-lg overflow-hidden flex items-center justify-center">
              <div className="w-full h-full bg-slate-800 relative flex items-center justify-center overflow-hidden">
                <div
                  className="absolute inset-0 opacity-60"
                  style={{
                    background:
                      'radial-gradient(circle at 30% 40%, rgba(239, 68, 68, 0.8) 0%, transparent 40%), radial-gradient(circle at 70% 60%, rgba(249, 115, 22, 0.7) 0%, transparent 50%), radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.4) 0%, transparent 70%)'
                  }}
                ></div>
                <div
                  className="absolute inset-0 opacity-10"
                  style={{
                    backgroundImage:
                      'linear-gradient(#94a3b8 1px, transparent 1px), linear-gradient(90deg, #94a3b8 1px, transparent 1px)',
                    backgroundSize: '40px 40px'
                  }}
                ></div>
                <div className="absolute inset-0 pointer-events-none opacity-20">
                  <div className="absolute top-1/2 left-0 w-full h-[1px] bg-white"></div>
                  <div className="absolute top-0 left-1/2 w-[1px] h-full bg-white"></div>
                </div>
                <div className="relative z-10 bg-slate-900/80 backdrop-blur-md border border-slate-700 px-6 py-4 rounded-lg shadow-2xl">
                  <p className="text-xs md:text-sm font-mono text-white tracking-wider text-center">
                    [ Grad-CAM XAI Output: Insert YOLOv8 Inference Image Here ]
                  </p>
                </div>
              </div>
              <div className="absolute inset-0 pointer-events-none mix-blend-screen bg-gradient-to-b from-transparent via-primary/5 to-transparent"></div>
            </div>
            <div className="p-4 flex justify-between items-center bg-surface-container-low">
              <p className="text-xs text-slate-400 font-medium">
                Grad-CAM Score: <span className="text-primary">0.942 Intensity</span>
              </p>
              <div className="flex gap-2">
                <span className="px-2 py-0.5 rounded bg-surface-container-highest text-[10px] text-on-surface-variant font-bold uppercase tracking-wider">
                  Ver 4.2 AI
                </span>
                <span className="px-2 py-0.5 rounded bg-surface-container-highest text-[10px] text-on-surface-variant font-bold uppercase tracking-wider">
                  Bovine-Specific
                </span>
              </div>
            </div>
          </section>

          <section className="lg:col-span-5 flex flex-col gap-8">
            <div className="bg-surface-container-high rounded-xl p-8 flex flex-col justify-center items-center text-center relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 blur-3xl -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors"></div>
              <p className="text-xs font-bold tracking-[0.2em] text-slate-400 uppercase mb-4">Calculated BCS</p>
              <div className="flex items-baseline gap-2">
                <h3 className="text-7xl font-black text-on-surface tracking-tighter">2.25</h3>
              </div>
              <p className="mt-4 px-4 py-1.5 bg-error-container text-on-error-container rounded-full text-xs font-bold uppercase tracking-wide">
                Under-conditioned
              </p>
              <div className="mt-8 w-full bg-surface-container-lowest h-2 rounded-full overflow-hidden">
                <div className="bg-error h-full" style={{ width: '45%' }}></div>
              </div>
              <div className="w-full flex justify-between mt-2 px-1">
                <span className="text-[10px] text-slate-500 font-bold uppercase">Severe</span>
                <span className="text-[10px] text-slate-500 font-bold uppercase">Optimal</span>
                <span className="text-[10px] text-slate-500 font-bold uppercase">Obese</span>
              </div>
            </div>

            <div className="bg-surface-container-high rounded-xl p-8 border-l-4 border-error/50">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
                    Overall Wellness Status
                  </p>
                  <h4 className="text-2xl font-extrabold text-error tracking-tight mt-1">AT RISK</h4>
                </div>
                <span
                  className="material-symbols-outlined text-error text-3xl"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  warning
                </span>
              </div>
              <div className="bg-surface-container-lowest rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-error/10 flex items-center justify-center">
                    <span className="material-symbols-outlined text-error text-xl">thermostat</span>
                  </div>
                  <div>
                    <p className="text-xs font-bold text-on-surface">Metabolic Stress Detected</p>
                    <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">
                      Detected high probability of ketosis risk due to rapid energy balance shift.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <section className="bg-surface-container-low rounded-xl p-8 relative overflow-hidden">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <span className="material-symbols-outlined text-primary text-2xl">assignment_turned_in</span>
              </div>
              <h3 className="text-xl font-bold text-white tracking-tight">Actionable Management Protocols</h3>
            </div>
            <button className="flex items-center gap-2 text-xs font-bold text-primary uppercase tracking-widest hover:opacity-80 transition-opacity">
              Export PDF
              <span className="material-symbols-outlined text-sm">download</span>
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-surface-container h-full p-6 rounded-lg group hover:bg-surface-container-high transition-colors">
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] font-black text-primary uppercase tracking-widest px-2 py-1 bg-primary/5 rounded">
                  Immediate
                </span>
                <span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">
                  air
                </span>
              </div>
              <p className="text-sm font-semibold text-white leading-relaxed">
                1. Immediate Action: Increase stall ventilation; local THI indicates severe heat stress.
              </p>
            </div>
            <div className="bg-surface-container h-full p-6 rounded-lg group hover:bg-surface-container-high transition-colors">
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] font-black text-primary uppercase tracking-widest px-2 py-1 bg-primary/5 rounded">
                  Nutrition
                </span>
                <span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">
                  restaurant
                </span>
              </div>
              <p className="text-sm font-semibold text-white leading-relaxed">
                2. Feeding: Shift 40% of feed ration to cooler evening hours to minimize digestive metabolic heat.
              </p>
            </div>
            <div className="bg-surface-container h-full p-6 rounded-lg group hover:bg-surface-container-high transition-colors">
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] font-black text-primary uppercase tracking-widest px-2 py-1 bg-primary/5 rounded">
                  Monitoring
                </span>
                <span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors">
                  medical_services
                </span>
              </div>
              <p className="text-sm font-semibold text-white leading-relaxed">
                3. Monitoring: Isolate animal to a shaded pen and ensure ad-libitum water access.
              </p>
            </div>
          </div>
          <div className="absolute -bottom-10 -right-10 opacity-5 pointer-events-none">
            <span className="material-symbols-outlined text-[12rem]">verified_user</span>
          </div>
        </section>
      </main>
    </div>
  )
}
