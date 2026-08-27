import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const SRI_LANKAN_DISTRICTS = [
  'Ampara',
  'Anuradhapura',
  'Badulla',
  'Batticaloa',
  'Colombo',
  'Galle',
  'Gampaha',
  'Hambantota',
  'Jaffna',
  'Kalutara',
  'Kandy',
  'Kegalle',
  'Kilinochchi',
  'Kurunegala',
  'Mannar',
  'Matale',
  'Matara',
  'Monaragala',
  'Mullaitivu',
  'Nuwara Eliya',
  'Polonnaruwa',
  'Puttalam',
  'Ratnapura',
  'Trincomalee',
  'Vavuniya'
]

export default function VetRegistration() {
  const navigate = useNavigate()
  const [errorMessage, setErrorMessage] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage("")
    setLoading(true)

    const formData = new FormData(e.target)
    const fullName = formData.get("full_name")?.trim()
    const email = formData.get("email")?.trim()
    const licenseNumber = formData.get("license_number")?.trim()
    const phone = formData.get("phone")?.trim()
    const district = formData.get("district")?.trim()
    const password = formData.get("password")
    const confirmPassword = formData.get("confirm_password")

    // Client-side email validation regex
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setErrorMessage("Please enter a valid email address.")
      setLoading(false)
      return
    }

    // Client-side password validation
    if (!password || password.length < 4) {
      setErrorMessage("Password must be at least 4 characters long.")
      setLoading(false)
      return
    }

    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match. Please re-enter.")
      setLoading(false)
      return
    }

    if (!licenseNumber) {
      setErrorMessage("Veterinary License / Council Registration Number is required.")
      setLoading(false)
      return
    }

    if (!phone || phone.length < 7) {
      setErrorMessage("Please provide a valid contact phone number (at least 7 digits).")
      setLoading(false)
      return
    }

    if (!district) {
      setErrorMessage("Please select your primary veterinary district jurisdiction.")
      setLoading(false)
      return
    }

    const role = formData.get("role") || "vet"

    const payload = {
      full_name: fullName,
      email: email,
      password: password,
      license_number: licenseNumber,
      phone: phone,
      district: district,
      role: role,
      assigned_farms: []
    }

    try {
      const response = await fetch("http://127.0.0.1:8000/api/vet/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (response.ok) {
        navigate('/health/vet-registration-success')
      } else {
        let errorMsg = "Registration failed. Please verify credentials."
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
        {/* Left Clinical Hero Section */}
        <section className="relative w-full md:w-5/12 lg:w-1/2 flex items-center justify-center p-8 lg:p-16 overflow-hidden min-h-[409px] md:min-h-screen">
          <div className="absolute inset-0 z-0">
            <div className="absolute inset-0 z-10 bg-gradient-to-r from-background/95 to-background/70"></div>
            <img
              className="w-full h-full object-cover grayscale opacity-40"
              alt="Veterinary clinical laboratory and livestock diagnostic environment"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuDOy71h00QnwxskGE3T9PHzccUn91c16LxPWAz4vJ-q9jQI6-GqcWRFWXMOvS3W8PejSACgDYENUiMj6PwLxRY4JvJdHM_FHRk26pGLtAGosAOxadR1FJbMk5PPNk1WFyYGJooxs1ki3ETYMq4WHCLMMEnSXVM3j8LZnA-37B8IbPnNV3_gadKa5rENPPx3-X28wnBXQ0Sy9_Y9L5HvqpG37eGzZoCYxooFXz8zT0B6ntyHi5bgOX6aE5-GVICQknaLqZuxY46uHA0o"
            />
          </div>
          <div className="relative z-20 flex flex-col items-center text-center max-w-md">
            <div className="mb-8 p-6 glass-panel rounded-xl border border-primary/20">
              <span
                className="material-symbols-outlined text-primary text-7xl mb-4"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                medical_services
              </span>
              <h1 className="text-3xl font-black tracking-tighter text-on-surface">ADRS Core</h1>
              <div className="h-1 w-12 bg-primary mx-auto mt-2 rounded-full"></div>
            </div>
            <span className="px-3 py-1 rounded-full bg-primary/10 border border-primary/30 text-primary text-xs font-mono font-bold uppercase tracking-widest mb-4">
              Professional Practitioner Portal
            </span>
            <h2 className="text-3xl lg:text-4xl font-extrabold tracking-tight text-white mb-4">
              Clinical Diagnostic Authority
            </h2>
            <p className="text-sm md:text-base text-on-surface-variant font-light leading-relaxed">
              Connect verified veterinary licenses to real-time herd health telemetries, computer vision triage, and multi-tier diagnostic reasoning.
            </p>
            <div className="mt-10 flex items-center space-x-6 text-on-surface-variant opacity-60">
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-primary">SLVC / VET</span>
                <span className="text-[0.625rem] tracking-widest uppercase">Certified</span>
              </div>
              <div className="w-px h-8 bg-outline-variant/30"></div>
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-primary">3-Tier</span>
                <span className="text-[0.625rem] tracking-widest uppercase">AI Engine</span>
              </div>
              <div className="w-px h-8 bg-outline-variant/30"></div>
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-primary">256-bit</span>
                <span className="text-[0.625rem] tracking-widest uppercase">Encrypted</span>
              </div>
            </div>
          </div>
        </section>

        {/* Right Form Section */}
        <section className="w-full md:w-7/12 lg:w-1/2 bg-surface-container-lowest flex items-center justify-center p-8 lg:p-20">
          <div className="w-full max-w-lg">
            <header className="mb-10">
              <span className="text-primary font-bold text-xs tracking-[0.2em] uppercase block mb-2">
                Professional Onboarding
              </span>
              <h3 className="text-3xl font-bold text-white mb-2">Register Professional Account</h3>
              <p className="text-on-surface-variant text-sm">
                Authorize your clinical or official credentials to access smart diagnostics, forecasting, and assigned livestock registries.
              </p>
            </header>

            {errorMessage && (
              <div className="mb-6 p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider flex items-center gap-2">
                <span className="material-symbols-outlined text-base">warning</span>
                <span>{errorMessage}</span>
              </div>
            )}

            <form className="space-y-5" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                  Account Type
                </label>
                <div className="flex flex-col sm:flex-row gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="role" value="vet" defaultChecked className="accent-primary" />
                    <span className="text-sm text-on-surface">Veterinary Officer</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="role" value="daph" className="accent-primary" />
                    <span className="text-sm text-on-surface">DAPH Official</span>
                  </label>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Full Name &amp; Title
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300 placeholder:text-slate-600"
                    name="full_name"
                    placeholder="Dr. Samantha Perera"
                    required
                    type="text"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Clinical Email Address
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300 placeholder:text-slate-600"
                    name="email"
                    placeholder="samantha@vet-council.org"
                    required
                    type="email"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Veterinary License / Reg No.
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300 placeholder:text-slate-600"
                    name="license_number"
                    placeholder="e.g., VET-LK-88902"
                    required
                    type="text"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Contact Phone Number
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300 placeholder:text-slate-600"
                    name="phone"
                    placeholder="+94 77 123 4567"
                    required
                    type="tel"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                  Primary Veterinary District Jurisdiction
                </label>
                <select
                  className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300"
                  name="district"
                  required
                  defaultValue=""
                >
                  <option value="" disabled className="bg-surface-container-high text-slate-500">
                    Select District Jurisdiction...
                  </option>
                  {SRI_LANKAN_DISTRICTS.map((dist) => (
                    <option key={dist} value={dist} className="bg-surface-container-high text-on-surface">
                      {dist} District
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Password
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300 placeholder:text-slate-600"
                    name="password"
                    placeholder="••••••••"
                    required
                    type="password"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-on-surface-variant">
                    Confirm Password
                  </label>
                  <input
                    className="w-full bg-surface-container border-none focus:ring-1 focus:ring-primary rounded-lg p-3 text-on-surface text-sm transition-all duration-300 placeholder:text-slate-600"
                    name="confirm_password"
                    placeholder="••••••••"
                    required
                    type="password"
                  />
                </div>
              </div>

              <div className="p-4 bg-surface-container-low rounded-xl border-l-4 border-primary/40 space-y-1">
                <p className="text-xs text-primary font-bold flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-base">verified</span>
                  Veterinary Council Professional Verification
                </p>
                <p className="text-[11px] text-slate-400">
                  By registering, your license registration will be mapped to assignable farm nodes and diagnostic case logs.
                </p>
              </div>

              <button
                className="w-full py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-sm tracking-widest uppercase rounded-lg shadow-[0_10px_30px_-10px_rgba(78,222,163,0.3)] hover:brightness-110 active:opacity-70 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                type="submit"
                disabled={loading}
              >
                {loading ? "Registering Clinical Practitioner..." : "Register Account"}
              </button>
            </form>

            <footer className="mt-8 text-center space-y-3">
              <p className="text-xs text-slate-400 uppercase tracking-tight">
                Already registered as a Vet?
                <Link className="text-primary hover:text-secondary-fixed transition-colors ml-1.5 font-bold" to="/health/vet-login">
                  Veterinarian Login
                </Link>
              </p>
              <div className="pt-3 border-t border-outline-variant/10">
                <Link
                  className="text-xs text-slate-400 hover:text-primary flex items-center justify-center gap-1.5 transition-colors font-medium"
                  to="/health/registration"
                >
                  <span className="material-symbols-outlined text-base">agriculture</span>
                  <span>Register Farm Node (Farm Owner / Manager)</span>
                </Link>
              </div>
            </footer>
          </div>
        </section>
      </div>

      {/* Global Footer */}
      <footer className="w-full flex flex-col md:flex-row justify-between items-center px-12 py-8 max-w-screen-2xl mx-auto bg-background border-t border-primary/10">
        <div className="text-primary font-black tracking-tighter mb-4 md:mb-0">SENTINEL AI VET PORTAL</div>
        <div className="flex flex-wrap justify-center gap-6 mb-4 md:mb-0">
          {['Clinical Protocol', 'Council Verification', 'Privacy Policy', 'Terms of Service'].map((t) => (
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
          © 2026 Sentinel AI Veterinary Diagnostics. Council Verified Intelligence.
        </div>
      </footer>
    </div>
  )
}
