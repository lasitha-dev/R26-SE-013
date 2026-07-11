import React from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function AddNewAnimal() {
  const navigate = useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault()
    // In a real application, you would handle API submission here.
    // For now, we will navigate back to the herd registry list.
    navigate('/health/herd-registry')
  }

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-8rem)]">
      <div className="max-w-2xl w-full">
        <div className="bg-surface-container-high rounded-xl p-6 md:p-10 relative overflow-hidden border border-outline-variant/10 shadow-2xl">
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/5 blur-[100px] rounded-full"></div>

          <div className="relative">
            <header className="mb-10">
              <h2 className="text-2xl font-black text-white tracking-tight uppercase">Register New Animal</h2>
              <p className="text-sm text-on-surface-variant mt-2 font-medium">
                Add a new subject to the Sentinel intelligence network.
              </p>
            </header>

            <form className="space-y-6" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                  Identifier (Tag ID or Name)
                </label>
                <input
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white placeholder:text-slate-600 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                  placeholder="e.g., #BT-8842 or Sudu"
                  type="text"
                  required
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">Gender</label>
                  <div className="relative">
                    <select
                      className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                      defaultValue=""
                      required
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
                      required
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
                      required
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
                      required
                    />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-500 uppercase">
                      KG
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
                <Link
                  className="text-sm font-bold text-slate-400 hover:text-white transition-colors tracking-wide underline underline-offset-8 decoration-slate-800 hover:decoration-white"
                  to="/health/herd-registry"
                >
                  Cancel
                </Link>
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

      <div className="fixed bottom-12 right-12 opacity-5 pointer-events-none select-none hidden xl:block">
        <span className="material-symbols-outlined text-[200px]" style={{ fontVariationSettings: "'wght' 100" }}>
          pets
        </span>
      </div>
    </div>
  )
}
