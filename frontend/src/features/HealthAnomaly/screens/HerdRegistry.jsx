export default function HerdRegistry() {
  const statusStyles = {
    primary: {
      pill: 'bg-primary/10 text-primary',
      dot: 'bg-primary',
    },
    error: {
      pill: 'bg-error/10 text-error',
      dot: 'bg-error',
    },
  }

  const rows = [
    {
      id: '#BT-8842',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '12-May-2020 (4 Yrs)',
      breed: 'Friesian',
      status: { label: 'Healthy', color: 'primary', pulse: false },
    },
    {
      id: 'Sudu',
      dot: 'bg-error',
      gender: 'Male',
      dob: '05-Jan-2021 (3 Yrs)',
      breed: 'Jersey',
      status: { label: 'At Risk', color: 'error', pulse: true },
    },
    {
      id: '#BT-7729',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '20-Oct-2019 (5 Yrs)',
      breed: 'Sahiwal',
      status: { label: 'Healthy', color: 'primary', pulse: false },
    },
    {
      id: 'Maanam',
      dot: 'bg-primary',
      gender: 'Female',
      dob: '15-Mar-2022 (2 Yrs)',
      breed: 'Local',
      status: { label: 'Healthy', color: 'primary', pulse: false },
    },
  ]

  return (
    <div className="text-on-surface antialiased overflow-hidden bg-surface min-h-screen">
      <aside className="h-screen w-64 fixed left-0 top-0 bg-surface-container-low border-r border-primary/10 flex flex-col py-6 tracking-tight z-50">
        <div className="px-6 mb-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary rounded flex items-center justify-center">
              <span
                className="material-symbols-outlined text-white text-xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                shield
              </span>
            </div>
            <div>
              <h1 className="text-white font-black tracking-widest leading-none">ADRS CORE</h1>
              <p className="text-[10px] uppercase tracking-[0.2em] text-primary/60 mt-1">Clinical Precision</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 space-y-1">
          <a
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-primary font-bold border-r-2 border-primary bg-primary/5 transition-all duration-200"
            href="#"
          >
            <span className="material-symbols-outlined text-[20px]">pets</span>
            <span className="text-sm">Herd Registry</span>
          </a>
          {[
            { icon: 'health_and_safety', label: 'Wellness & BCS' },
            { icon: 'memory', label: 'AI Smart Diagnosis' },
            { icon: 'map', label: 'Geospatial Intelligence' },
            { icon: 'partly_cloudy_day', label: 'Seasonal Forecasting' },
          ].map((item) => (
            <a
              key={item.label}
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:text-primary-fixed hover:bg-primary/10 transition-all duration-200"
              href="#"
            >
              <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
              <span className="text-sm">{item.label}</span>
            </a>
          ))}
        </nav>

        <div className="px-4 pb-6 mt-auto">
          <div className="space-y-1">
            {[
              { icon: 'settings', label: 'Settings' },
              { icon: 'help', label: 'Support' },
            ].map((item) => (
              <a
                key={item.label}
                className="flex items-center gap-3 px-4 py-2 text-slate-400 hover:text-primary-fixed transition-colors"
                href="#"
              >
                <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                <span className="text-sm">{item.label}</span>
              </a>
            ))}
          </div>
        </div>
      </aside>

      <header className="fixed top-0 right-0 w-[calc(100%-16rem)] h-16 bg-surface/80 backdrop-blur-xl z-40 flex items-center justify-between px-8">
        <div className="flex items-center bg-surface-container-low/50 rounded-full px-4 py-1.5 w-96 group focus-within:ring-1 focus-within:ring-primary/20 transition-all">
          <span className="material-symbols-outlined text-slate-400 text-sm">search</span>
          <input
            className="bg-transparent border-none text-sm focus:ring-0 text-on-surface w-full placeholder:text-slate-500"
            placeholder="Search by Tag ID or Breed"
            type="text"
          />
        </div>
        <div className="flex items-center gap-6">
          <button className="text-slate-400 hover:text-primary transition-colors relative" type="button">
            <span className="material-symbols-outlined">notifications_active</span>
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-error rounded-full border-2 border-surface"></span>
          </button>
          <div className="flex items-center gap-3 pl-6 border-l border-slate-700/50">
            <div className="text-right">
              <p className="text-sm font-bold text-white tracking-tight leading-none">Kamal Perera</p>
              <p className="text-[10px] text-primary font-medium tracking-widest uppercase mt-1">Dairy Farmer</p>
            </div>
            <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-primary/20">
              <img
                alt="Veterinary Practitioner Avatar"
                data-alt="A professional headshot of a middle-aged South Asian man with a friendly expression. He is wearing a clean, modern work shirt suitable for a veterinary or agricultural management role. The background is a soft-focus office interior with warm, cinematic lighting that highlights his facial features while maintaining a professional clinical atmosphere."
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuBXDw0jk_0i-nQIWtaOR19WJzJ-mJDy8gIgfX3LhfZ8JDlxoH4Dvv4Kcqfqp5mU4OzVU4s1VO9WSnzSkVjgOk3KwCPYplw48SscqR_4ZoxDsNRCUvudemWo8tOa1kVE_ZEGsw1iAFndD9SLJ5woqUlq1Q6HvdZT3_NKLyYZjK7WsLze0aOESeZ2lXNak2fTzp0S1PF7VNbqKoGoaBRyiyBgoCA5AGVgdKITINGA5clhnPVpeASHT92nsni1C4-FRDu8mrwoXH4ziiuX"
              />
            </div>
          </div>
        </div>
      </header>

      <main className="ml-64 pt-24 p-8 min-h-screen bg-surface overflow-auto">
        <div className="flex items-end justify-between mb-8">
          <div className="space-y-1">
            <h2 className="text-3xl font-black tracking-tight text-white uppercase">HERD REGISTRY &amp; MANAGEMENT</h2>
            <div className="flex items-center gap-4 text-slate-400 text-xs tracking-widest uppercase font-medium">
              <span className="flex items-center gap-1">
                <span className="w-1 h-1 bg-primary rounded-full"></span> 42 Total Livestock
              </span>
              <span className="flex items-center gap-1">
                <span className="w-1 h-1 bg-secondary rounded-full"></span> 98% Bio-Security Score
              </span>
              <span className="flex items-center gap-1">
                <span className="w-1 h-1 bg-error rounded-full"></span> 1 Pending Alert
              </span>
            </div>
          </div>
          <button
            className="px-6 py-3 bg-primary-container text-on-primary-container font-bold rounded-lg flex items-center gap-2 hover:opacity-90 transition-all active:scale-[0.98]"
            type="button"
          >
            <span className="material-symbols-outlined">add</span>
            + Add New Animal
          </button>
        </div>

        <div className="grid grid-cols-12 gap-6 mb-8">
          <div className="col-span-12 lg:col-span-8 bg-surface-container-low rounded-xl p-6 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
              <span className="material-symbols-outlined text-[120px] text-primary">analytics</span>
            </div>
            <div className="relative z-10">
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-6">Population Health Trends</h3>
              <div className="flex items-end gap-2 h-32 px-2">
                {[60, 75, 55, 90, 85, 95].map((h, idx) => (
                  <div
                    key={idx}
                    className="w-full bg-primary/20 rounded-t hover:bg-primary/40 transition-all"
                    style={{ height: `${h}%` }}
                  ></div>
                ))}
                <div className="w-full bg-primary rounded-t hover:bg-primary/80 transition-all relative" style={{ height: '80%' }}>
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-surface text-primary text-[10px] font-bold px-2 py-1 rounded border border-primary/20 whitespace-nowrap">
                    OPT-MAX
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-12 lg:col-span-4 bg-surface-container-low rounded-xl p-6 flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Breed Composition</h3>
              <p className="text-xs text-slate-500">Distribution analysis across primary herds</p>
            </div>
            <div className="space-y-3 mt-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium">Friesian</span>
                <span className="text-xs font-bold text-primary">64%</span>
              </div>
              <div className="w-full h-1 bg-surface rounded-full overflow-hidden">
                <div className="h-full bg-primary w-[64%]"></div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium">Jersey</span>
                <span className="text-xs font-bold text-secondary">22%</span>
              </div>
              <div className="w-full h-1 bg-surface rounded-full overflow-hidden">
                <div className="h-full bg-secondary w-[22%]"></div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-surface-container-low rounded-xl overflow-hidden">
          <div className="px-8 py-6 flex items-center justify-between border-b border-surface/50">
            <h3 className="text-lg font-bold text-white tracking-tight">Active Animal Registry</h3>
            <div className="flex items-center gap-2">
              <button
                className="p-2 hover:bg-surface-container-high rounded transition-colors text-slate-400"
                type="button"
              >
                <span className="material-symbols-outlined">filter_list</span>
              </button>
              <button
                className="p-2 hover:bg-surface-container-high rounded transition-colors text-slate-400"
                type="button"
              >
                <span className="material-symbols-outlined">download</span>
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-container-lowest/50 text-slate-400 text-[10px] uppercase tracking-[0.2em] font-bold">
                  <th className="px-8 py-4">Identifier (Tag / Name)</th>
                  <th className="px-6 py-4">Gender</th>
                  <th className="px-6 py-4">DOB &amp; Age</th>
                  <th className="px-6 py-4">Breed</th>
                  <th className="px-6 py-4">Current Health Status</th>
                  <th className="px-8 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface/30">
                {rows.map((r) => (
                  <tr key={r.id} className="group hover:bg-surface-container-high/30 transition-colors">
                    <td className="px-8 py-5">
                      <div className="flex items-center gap-3">
                        <span className={`w-2 h-2 rounded-full ${r.dot}`}></span>
                        <span className="font-mono text-sm font-bold text-white">{r.id}</span>
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <span className="text-sm text-on-surface/80">{r.gender}</span>
                    </td>
                    <td className="px-6 py-5">
                      <span className="text-sm font-medium text-on-surface/80 whitespace-nowrap">{r.dob}</span>
                    </td>
                    <td className="px-6 py-5">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-slate-500 text-lg">category</span>
                        <span className="text-sm">{r.breed}</span>
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full ${statusStyles[r.status.color].pill} text-[10px] font-bold uppercase tracking-wider`}
                      >
                        <span
                          className={`w-1 h-1 rounded-full ${statusStyles[r.status.color].dot} ${r.status.pulse ? 'animate-pulse' : ''}`}
                        ></span>
                        {r.status.label}
                      </span>
                    </td>
                    <td className="px-8 py-5 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          className="p-2 text-slate-400 hover:text-primary transition-colors hover:bg-primary/5 rounded-lg"
                          type="button"
                        >
                          <span className="material-symbols-outlined text-xl">visibility</span>
                        </button>
                        <button
                          className="p-2 text-slate-400 hover:text-secondary transition-colors hover:bg-secondary/5 rounded-lg"
                          type="button"
                        >
                          <span className="material-symbols-outlined text-xl">edit</span>
                        </button>
                        <button
                          className="p-2 text-slate-400 hover:text-error transition-colors hover:bg-error/5 rounded-lg"
                          type="button"
                        >
                          <span className="material-symbols-outlined text-xl">delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="px-8 py-4 bg-surface-container-lowest/30 flex items-center justify-between">
            <p className="text-xs text-slate-500 font-medium">
              Showing <span className="text-on-surface">4</span> of <span className="text-on-surface">42</span> tracked
              animals
            </p>
            <div className="flex items-center gap-2">
              <button className="p-1.5 hover:bg-surface-container-high rounded-lg text-slate-400 transition-colors" type="button">
                <span className="material-symbols-outlined text-lg">chevron_left</span>
              </button>
              <div className="flex gap-1">
                <button className="w-8 h-8 rounded-lg bg-primary/10 text-primary text-xs font-bold border border-primary/20" type="button">
                  1
                </button>
                <button className="w-8 h-8 rounded-lg hover:bg-surface-container-high text-slate-400 text-xs font-bold transition-colors" type="button">
                  2
                </button>
                <button className="w-8 h-8 rounded-lg hover:bg-surface-container-high text-slate-400 text-xs font-bold transition-colors" type="button">
                  3
                </button>
              </div>
              <button className="p-1.5 hover:bg-surface-container-high rounded-lg text-slate-400 transition-colors" type="button">
                <span className="material-symbols-outlined text-lg">chevron_right</span>
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
