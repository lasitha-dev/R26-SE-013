import React from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function RegistrationLanding() {
  const navigate = useNavigate()
  const [errorMessage, setErrorMessage] = React.useState("")
  const [loading, setLoading] = React.useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage("")
    setLoading(true)

    const formData = new FormData(e.target)
    const email = formData.get("email")
    const password = formData.get("password")

    // Client-side email validation regex
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setErrorMessage("Please enter a valid email address.")
      setLoading(false)
      return
    }

    // Client-side password validation
    if (password.length < 4) {
      setErrorMessage("Password must be at least 4 characters long.")
      setLoading(false)
      return
    }

    const payload = {
      owner_name: formData.get("owner_name"),
      email: email,
      password: password,
      location_district: "Pending Map Selection",
      registration_number: formData.get("registration_number") || null,
      veterinarian_name: formData.get("veterinarian_name"),
      total_animals: parseInt(formData.get("total_animals") || "0", 10)
    }

    try {
      const response = await fetch("http://127.0.0.1:8000/api/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (response.ok) {
        navigate('/health/registration-success')
      } else {
        // Render server validation errors clearly
        let errorMsg = "Registration failed. Please check details and try again."
        if (data && data.detail) {
          if (typeof data.detail === "string") {
            errorMsg = data.detail
          } else if (Array.isArray(data.detail)) {
            errorMsg = data.detail.map(err => `${err.loc[err.loc.length - 1]}: ${err.msg}`).join(", ")
          }
        }
        setErrorMessage(errorMsg)
      }
    } catch (err) {
      setErrorMessage("Cannot connect to server. Ensure backend is running.")
    } finally {
      setLoading(false)
    }
  }

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

            {errorMessage && (
              <div className="mb-6 p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider">
                {errorMessage}
              </div>
            )}

            <form
              className="space-y-6"
              onSubmit={handleSubmit}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Owner&apos;s Full Name
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    name="owner_name"
                    placeholder="Dr. Julian Vane"
                    required
                    type="text"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Email Address
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    name="email"
                    placeholder="vane.j@sentinel-ai.vet"
                    required
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
                    name="password"
                    placeholder="••••••••"
                    required
                    type="password"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Registration Number (Optional)
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    name="registration_number"
                    placeholder="e.g., REG-AI-9902"
                    type="text"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Veterinarian Name
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                    name="veterinarian_name"
                    placeholder="Clinic Lead"
                    required
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
                    name="total_animals"
                    placeholder="0"
                    required
                    type="number"
                  />
                </div>
              </div>

              <button
                className="w-full py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-sm tracking-widest uppercase rounded-lg shadow-[0_10px_30px_-10px_rgba(78,222,163,0.3)] hover:brightness-110 active:opacity-70 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                type="submit"
                disabled={loading}
              >
                {loading ? "Registering Node..." : "Register Farm"}
              </button>
            </form>

            <footer className="mt-8 text-center space-y-3">
              <p className="text-xs text-slate-500 uppercase tracking-tighter">
                Already registered?
                <Link className="text-primary hover:text-secondary-fixed transition-colors ml-1" to="/health/login">
                  System Login
                </Link>
              </p>
              <div className="pt-3 border-t border-outline-variant/10">
                <Link
                  className="text-xs text-slate-400 hover:text-primary flex items-center justify-center gap-1.5 transition-colors font-medium"
                  to="/health/vet-registration"
                >
                  <span className="material-symbols-outlined text-base">medical_services</span>
                  <span>Register as Veterinarian (Vet Authority)</span>
                </Link>
              </div>
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
