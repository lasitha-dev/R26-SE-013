import React from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function RegistrationLanding() {
  const navigate = useNavigate()

  return (
    <div className="bg-background text-on-surface font-body antialiased overflow-x-hidden min-h-screen">
      <div className="flex flex-col md:flex-row min-h-screen w-full">
        <section className="relative w-full md:w-5/12 lg:w-1/2 flex items-center justify-center p-8 lg:p-16 overflow-hidden min-h-[409px] md:min-h-screen">
          <div className="absolute inset-0 z-0">
            <div className="absolute inset-0 z-10 bg-gradient-to-r from-background/95 to-background/70"></div>
            <img
              className="w-full h-full object-cover grayscale opacity-40"
              data-alt="A high-tech agricultural landscape at night with glowing data overlays and digital wireframes of livestock. The scene is bathed in a deep midnight blue atmosphere with vibrant emerald green laser lines highlighting animal contours. The mood is clinical, futuristic, and sophisticated, emphasizing precision surveillance and AI-driven veterinary diagnostics in a vast, dark pasture setting."
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuDOy71h00QnwxskGE3T9PHzccUn91c16LxPWAz4vJ-q9jQI6-GqcWRFWXMOvS3W8PejSACgDYENUiMj6PwLxRY4JvJdHM_FHRk26pGLtAGosAOxadR1FJbMk5PPNk1WFyYGJooxs1ki3ETYMq4WHCLMMEnSXVM3j8LZnA-37B8IbPnNV3_gadKa5rENPPx3-X28wnBXQ0Sy9_Y9L5HvqpG37eGzZoCYxooFXz8zT0B6ntyHi5bgOX6aE5-GVICQknaLqZuxY46uHA0o"
            />
          </div>
          <div className="relative z-20 flex flex-col items-center text-center max-w-md">
            <div className="mb-8 p-6 glass-panel rounded-xl">
              <span
                className="material-symbols-outlined text-primary text-7xl mb-4"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                shield_with_heart
              </span>
              <h1 className="text-3xl font-black tracking-tighter text-on-surface">ADRS Core</h1>
              <div className="h-1 w-12 bg-primary mx-auto mt-2 rounded-full"></div>
            </div>
            <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-white mb-4">
              Precision Livestock Surveillance
            </h2>
            <p className="text-lg text-on-surface-variant font-light leading-relaxed">
              Deploying enterprise-grade AI diagnostic reporting for the next generation of veterinary clinical
              intelligence.
            </p>
            <div className="mt-12 flex items-center space-x-6 text-on-surface-variant opacity-60">
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-primary">99.9%</span>
                <span className="text-[0.625rem] tracking-widest uppercase">Uptime</span>
              </div>
              <div className="w-px h-8 bg-outline-variant/30"></div>
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-primary">2ms</span>
                <span className="text-[0.625rem] tracking-widest uppercase">Latency</span>
              </div>
              <div className="w-px h-8 bg-outline-variant/30"></div>
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-primary">256-bit</span>
                <span className="text-[0.625rem] tracking-widest uppercase">Encryption</span>
              </div>
            </div>
          </div>
        </section>

        <section className="w-full md:w-7/12 lg:w-1/2 bg-surface-container-lowest flex items-center justify-center p-8 lg:p-24">
          <div className="w-full max-w-lg">
            <header className="mb-12">
              <span className="text-primary font-bold text-xs tracking-[0.2em] uppercase block mb-3">
                Institutional Access
              </span>
              <h3 className="text-3xl font-bold text-white mb-2">Register Farm</h3>
              <p className="text-on-surface-variant">Initialize your diagnostic node within the Sentinel network.</p>
            </header>

            <form
              className="space-y-6"
              onSubmit={(e) => {
                e.preventDefault()
                navigate('/health/registration-success')
              }}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Owner&apos;s Full Name
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    placeholder="Dr. Julian Vane"
                    type="text"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Email Address
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    placeholder="vane.j@sentinel-ai.vet"
                    type="email"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Password
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    placeholder="••••••••"
                    type="password"
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Farm Location (District)
                  </label>
                  <div className="relative">
                    <select
                      className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 pr-10 text-on-surface text-sm appearance-none transition-all duration-300"
                      defaultValue=""
                    >
                      <option disabled value="">
                        Select District
                      </option>
                      <option value="north">Northern Highlands</option>
                      <option value="central">Central Plains</option>
                      <option value="south">Southern Delta</option>
                      <option value="east">Eastern Corridor</option>
                    </select>
                    <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-primary pointer-events-none">
                      expand_more
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Registration Number
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    placeholder="REG-AI-9902"
                    type="text"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Veterinarian Name
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    placeholder="Clinic Lead"
                    type="text"
                  />
                </div>
              </div>

              <div className="space-y-6 bg-surface-container-low p-6 rounded-xl border-l-4 border-primary/20">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Total Animals
                  </label>
                  <input
                    className="w-full bg-surface-container-highest border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    min="0"
                    placeholder="0"
                    type="number"
                  />
                </div>

                <div className="space-y-3">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Cattle Breeds (Multi-select)
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {['Jersey', 'Friesian', 'Sahiwal', 'Angus'].map((breed) => (
                      <label
                        key={breed}
                        className="flex items-center space-x-3 p-3 bg-surface-container rounded-lg cursor-pointer hover:bg-surface-container-high transition-colors"
                      >
                        <input
                          className="rounded text-primary focus:ring-primary bg-surface-container-highest border-none"
                          type="checkbox"
                        />
                        <span className="text-sm font-medium">{breed}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              <button
                className="w-full py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-sm tracking-widest uppercase rounded-lg shadow-[0_10px_30px_-10px_rgba(78,222,163,0.3)] hover:brightness-110 active:opacity-70 transition-all duration-300"
                type="submit"
              >
                Register Farm
              </button>
            </form>

            <footer className="mt-8 text-center">
              <p className="text-xs text-slate-500 uppercase tracking-tighter">
                Already registered?
                <Link className="text-primary hover:text-secondary-fixed transition-colors ml-1" to="/health/login">
                  System Login
                </Link>
              </p>
            </footer>
          </div>
        </section>
      </div>

      <footer className="w-full flex flex-col md:flex-row justify-between items-center px-12 py-8 max-w-screen-2xl mx-auto bg-background border-t border-primary/10">
        <div className="text-primary font-black tracking-tighter mb-4 md:mb-0">SENTINEL AI</div>
        <div className="flex flex-wrap justify-center gap-6 mb-4 md:mb-0">
          {['Privacy Policy', 'Terms of Service', 'Clinical Protocol', 'Technical Documentation'].map((t) => (
            <a
              key={t}
              className="text-[0.6875rem] tracking-[0.05em] uppercase text-slate-400 hover:text-primary transition-colors duration-300"
              href="#"
            >
              {t}
            </a>
          ))}
        </div>
        <div className="text-[0.6875rem] tracking-[0.05em] uppercase text-slate-400 text-center md:text-right">
          © 2024 Sentinel AI Veterinary Diagnostics. Precision Engineered Intelligence.
        </div>
      </footer>
    </div>
  )
}
