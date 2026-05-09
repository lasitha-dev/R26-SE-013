export default function AddNewAnimal() {
  return (
    <div className="flex min-h-screen overflow-hidden bg-surface text-on-surface">
      <aside className="fixed left-0 top-0 h-full w-72 bg-surface-container-low flex flex-col py-8 z-50">
        <div className="px-8 mb-10 flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-container rounded flex items-center justify-center">
            <span
              className="material-symbols-outlined text-on-primary-container"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              shield
            </span>
          </div>
          <div>
            <h1 className="text-white font-black text-xl tracking-tight leading-none">ADRS CORE</h1>
            <p className="text-[10px] font-bold tracking-widest text-slate-500 mt-1 uppercase">CLINICAL PRECISION</p>
          </div>
        </div>

        <nav className="flex-grow space-y-1">
          <a
            className="flex items-center gap-4 px-8 py-3 text-primary bg-surface-container-high border-r-2 border-primary transition-all"
            href="#"
          >
            <span className="material-symbols-outlined">pets</span>
            <span className="text-sm font-semibold tracking-wide uppercase">Herd Registry</span>
          </a>
          {[
            { icon: 'health_and_safety', label: 'Wellness & BCS' },
            { icon: 'psychology', label: 'AI Smart Diagnosis' },
            { icon: 'map', label: 'Geospatial Intelligence' },
            { icon: 'wb_sunny', label: 'Seasonal Forecasting' },
          ].map((item) => (
            <a
              key={item.label}
              className="flex items-center gap-4 px-8 py-3 text-slate-400 hover:text-white hover:bg-white/5 transition-all"
              href="#"
            >
              <span className="material-symbols-outlined">{item.icon}</span>
              <span className="text-sm font-medium">{item.label}</span>
            </a>
          ))}
        </nav>

        <div className="px-4 mt-auto space-y-4">
          <div className="pt-4 border-t border-white/5 space-y-1">
            {[
              { icon: 'settings', label: 'Settings' },
              { icon: 'help', label: 'Support' },
            ].map((item) => (
              <a
                key={item.label}
                className="flex items-center gap-4 px-4 py-2 text-slate-400 hover:text-white transition-colors"
                href="#"
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                <span className="text-xs font-semibold tracking-wider uppercase">{item.label}</span>
              </a>
            ))}
          </div>
        </div>
      </aside>

      <main className="flex-grow ml-72 relative flex flex-col h-screen overflow-y-auto no-scrollbar bg-surface">
        <header className="sticky top-0 w-full flex justify-between items-center px-8 py-6 z-40 bg-surface/80 backdrop-blur-md">
          <div>
            <nav className="flex items-center gap-2 text-xs font-bold tracking-widest text-slate-500 uppercase">
              <span className="hover:text-primary transition-colors cursor-pointer">SENTINEL</span>
              <span className="material-symbols-outlined text-[10px]">chevron_right</span>
              <span className="text-on-surface">HERD REGISTRY</span>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-bold text-white leading-none">Kamal Perera</p>
              <p className="text-[10px] font-semibold text-primary tracking-widest uppercase mt-1">Dairy Farmer</p>
            </div>
            <div className="w-10 h-10 rounded-full border-2 border-primary/20 p-0.5">
              <img
                alt="User profile avatar for Kamal Perera"
                className="w-full h-full object-cover rounded-full"
                data-alt="A professional headshot of a mature South Asian male dairy farmer in outdoor attire. The lighting is warm and natural, suggesting a sunset at a farm. The image has a clean, high-end editorial quality with a shallow depth of field, focusing on his friendly yet authoritative expression."
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDCUBz6RWQYgosV0oUM6lWrPFEIMBYiwilWzfSt3LRrGcoVOLrvjHu2vsXad_NMJNsJrIjap0IKxNPoKFc_w-H0rXhKQbb9ZKtVginXodaQlTN9QgMP6TbdGDlbo6EB9izFG09mpv2ryFU3ciI8ouVVWek5LP7nxFBL8AbrqcfXtX1-z3pe_auyHymhjuQodX3zpRHf7hTDFMhrXNLkr-3dNCz6ns0ex1p1iwx9y7ojaNL6Flm_NinXt4BRoZ2WiMIhBrZ_KCk0eeHQ"
              />
            </div>
          </div>
        </header>

        <section className="flex-grow flex items-center justify-center px-8 pb-12">
          <div className="max-w-2xl w-full">
            <div className="bg-surface-container-high rounded-xl p-10 relative overflow-hidden border border-outline-variant/10 shadow-2xl">
              <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/5 blur-[100px] rounded-full"></div>

              <div className="relative">
                <header className="mb-10">
                  <h2 className="text-2xl font-black text-white tracking-tight uppercase">Register New Animal</h2>
                  <p className="text-sm text-on-surface-variant mt-2 font-medium">
                    Add a new subject to the Sentinel intelligence network.
                  </p>
                </header>

                <form className="space-y-6" onSubmit={(e) => e.preventDefault()}>
                  <div className="space-y-2">
                    <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                      Identifier (Tag ID or Name)
                    </label>
                    <input
                      className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white placeholder:text-slate-600 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                      placeholder="e.g., #BT-8842 or Sudu"
                      type="text"
                      defaultValue=""
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">Gender</label>
                      <div className="relative">
                        <select
                          className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                          defaultValue=""
                        >
                          <option disabled value="">
                            Select Gender
                          </option>
                          <option value="female">Female</option>
                          <option value="male">Male</option>
                        </select>
                        <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                          expand_more
                        </span>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                        Date of Birth (DOB)
                      </label>
                      <div className="relative">
                        <input
                          className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all [color-scheme:dark]"
                          type="date"
                          defaultValue=""
                        />
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">Breed</label>
                      <div className="relative">
                        <select
                          className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                          defaultValue=""
                        >
                          <option disabled value="">
                            Select Breed
                          </option>
                          <option value="friesian">Friesian</option>
                          <option value="jersey">Jersey</option>
                          <option value="sahiwal">Sahiwal</option>
                          <option value="local">Local</option>
                        </select>
                        <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                          expand_more
                        </span>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                        Initial Body Weight (KG)
                      </label>
                      <div className="relative">
                        <input
                          className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white placeholder:text-slate-600 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                          placeholder="0.00"
                          type="number"
                          defaultValue=""
                        />
                        <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-500 uppercase">
                          KG
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
                    <a
                      className="text-sm font-bold text-slate-400 hover:text-white transition-colors tracking-wide underline underline-offset-8 decoration-slate-800 hover:decoration-white"
                      href="#"
                    >
                      Cancel
                    </a>
                    <button
                      className="w-full md:w-auto px-10 py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-lg font-black text-sm uppercase tracking-widest shadow-xl shadow-primary/20 transition-transform active:scale-[0.98]"
                      type="submit"
                    >
                      Save Animal Record
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <div className="mt-8 flex items-center justify-center gap-6 text-[10px] font-bold tracking-[0.2em] text-slate-600 uppercase">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-primary rounded-full"></span>
                Encrypted Connection
              </div>
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-primary rounded-full"></span>
                AI Validation Active
              </div>
            </div>
          </div>
        </section>

        <div className="fixed bottom-0 right-0 p-12 opacity-5 pointer-events-none select-none">
          <span className="material-symbols-outlined text-[300px]" style={{ fontVariationSettings: "'wght' 100" }}>
            pets
          </span>
        </div>
      </main>
    </div>
  )
}
