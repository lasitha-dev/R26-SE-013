import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export default function VetLogin() {
  const navigate = useNavigate()
  const [errorMessage, setErrorMessage] = useState("")
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    setErrorMessage("")
    setLoading(true)

    const formData = new FormData(e.target)
    const email = formData.get("email")
    const password = formData.get("password")

    try {
      const response = await fetch(`${API_BASE}/api/vet/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email, password })
      })

      const data = await response.json()
      if (response.ok) {
        const userRole = data.role
        if (userRole === "vet" || userRole === "daph") {
          localStorage.setItem("token", data.access_token)
          localStorage.setItem("full_name", data.full_name)
          localStorage.setItem("owner_name", data.full_name)
          localStorage.setItem("veterinarian_name", data.full_name)
          localStorage.setItem("email", data.email)
          localStorage.setItem("role", userRole)
          localStorage.setItem("license_number", data.license_number || "")
          localStorage.setItem("phone", data.phone || "")
          localStorage.setItem("district", data.district || "")
          
          if (userRole === "daph") {
            navigate('/vet/forecasting')
          } else {
            navigate('/vet/dashboard')
          }
        } else {
          // Unsupported or missing role
          localStorage.removeItem("token")
          localStorage.removeItem("role")
          setErrorMessage("Authentication failed. Unsupported professional role.")
        }
      } else {
        setErrorMessage(data.detail || "Authentication failed. Please verify clinical credentials.")
      }
    } catch (err) {
      setErrorMessage("Cannot connect to server. Ensure backend is running.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-6 overflow-hidden bg-surface text-on-surface">
      <main className="w-full max-w-md">
        <div className="absolute inset-0 z-[-1] pointer-events-none opacity-20">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary/20 blur-[120px]"></div>
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-secondary/10 blur-[120px]"></div>
        </div>

        <div className="relative">
          <div className="flex flex-col items-center mb-8">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-12 h-12 flex items-center justify-center rounded-xl bg-primary-container/20 text-primary shadow-glow-sm">
                <span
                  className="material-symbols-outlined text-3xl"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  health_and_safety
                </span>
              </div>
              <span className="text-2xl font-black tracking-tighter text-on-surface uppercase">ADRS Core</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-[10px] font-mono font-bold uppercase tracking-widest">
                Veterinary Portal
              </span>
              <span className="text-slate-600 text-xs">•</span>
              <p className="text-[0.6875rem] tracking-[0.15em] uppercase text-slate-400 font-bold">
                Clinical Diagnostics Access
              </p>
            </div>
          </div>

          <section className="bg-surface-container-high rounded-xl p-8 md:p-10 shadow-2xl shadow-black/50 border border-outline-variant/10">
            <div className="mb-8">
              <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold tracking-tight text-on-surface">Veterinarian Login</h1>
                <span className="text-primary material-symbols-outlined text-2xl">verified_user</span>
              </div>
              <p className="text-sm text-slate-400 mt-2">Authorized clinical practitioners &amp; veterinary officers.</p>
            </div>

            {errorMessage && (
              <div className="mb-6 p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider flex items-center gap-2">
                <span className="material-symbols-outlined text-base">warning</span>
                <span>{errorMessage}</span>
              </div>
            )}

            <form
              className="space-y-6"
              onSubmit={handleLogin}
            >
              <div className="space-y-2">
                <label
                  className="text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-slate-400"
                  htmlFor="email"
                >
                  Clinical Email Address
                </label>
                <div className="relative group">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-500 group-focus-within:text-primary transition-colors">
                    alternate_email
                  </span>
                  <input
                    className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3.5 pl-12 pr-4 text-on-surface placeholder:text-slate-600 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/20 transition-all text-sm"
                    id="email"
                    name="email"
                    placeholder="doctor@veterinary-council.gov"
                    required
                    type="email"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label
                    className="text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-slate-400"
                    htmlFor="password"
                  >
                    Password
                  </label>
                  <Link
                    className="text-[0.6875rem] font-bold text-primary hover:text-primary-fixed-dim transition-colors uppercase tracking-wider"
                    to="/health/password-reset"
                  >
                    Forgot Password?
                  </Link>
                </div>
                <div className="relative group">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-500 group-focus-within:text-primary transition-colors">
                    lock
                  </span>
                  <input
                    className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3.5 pl-12 pr-4 text-on-surface placeholder:text-slate-600 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/20 transition-all text-sm"
                    id="password"
                    name="password"
                    placeholder="••••••••"
                    required
                    type="password"
                  />
                </div>
              </div>

              <button
                className="w-full bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold py-4 rounded-lg shadow-lg shadow-primary/10 hover:opacity-90 active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed uppercase text-sm tracking-wider"
                type="submit"
                disabled={loading}
              >
                <span className="material-symbols-outlined text-xl">login</span>
                {loading ? "Authenticating Practitioner..." : "Access Clinical Workbench"}
              </button>
            </form>

            <div className="mt-8 flex items-center justify-center gap-3">
              <div className="h-[1px] flex-grow bg-outline-variant/10"></div>
              <span className="text-[0.625rem] text-slate-500 uppercase tracking-widest whitespace-nowrap">
                Veterinary Council Auth Protocol
              </span>
              <div className="h-[1px] flex-grow bg-outline-variant/10"></div>
            </div>

            <div className="mt-6 space-y-3 text-center">
              <p className="text-sm text-slate-400">
                New practitioner?
                <Link
                  className="text-primary font-bold hover:underline underline-offset-4 ml-1.5 transition-all"
                  to="/health/vet-registration"
                >
                  Register as Veterinarian
                </Link>
              </p>
              
              <div className="pt-3 border-t border-outline-variant/10">
                <Link
                  className="text-xs text-slate-400 hover:text-primary flex items-center justify-center gap-1.5 transition-colors font-medium"
                  to="/health/login"
                >
                  <span className="material-symbols-outlined text-base">agriculture</span>
                  <span>Farm Owner / Livestock Manager Login</span>
                </Link>
              </div>
            </div>
          </section>

          <div className="mt-12 flex justify-center opacity-30 grayscale hover:grayscale-0 transition-all duration-700">
            <div className="w-32 h-32 rounded-full border-4 border-dashed border-primary/20 animate-spin-slow relative flex items-center justify-center overflow-hidden">
              <img
                className="w-full h-full object-cover"
                data-alt="A highly detailed close-up of a digital veterinary diagnostic interface showing complex cellular structures and glowing DNA helices. The color scheme is dominated by deep obsidian blues and vibrant clinical greens. The aesthetic is clean and futuristic, representing advanced AI analysis in animal disease detection. Soft lighting highlights the intricate data points and glowing neural network connections in the background."
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuBK04T5fDljlkQiRc-muMZWLojvKRFaASfTHBgWOD-Lp8lIyLBtJMHYUnavv7uSzoRrIgU8WpzKWqMF3wXh2fjXV7uqx9CGq2289Bp8Igih0DgxBrYb7JXFh42x27AlhPYWYZdazyIEfg815nTHa1hnVumsMZdgVkdUTXp5tgXaA5oq65DPdUwZRBPQ3g_P-pEEAX5TXBVnkUxnhQkIwtm_KG3LtZrFpJg0Yo4lqjSRouDLAyIVDFkretZz7zviUlU4auctoJUEXvW4"
              />
            </div>
          </div>
        </div>

        <footer className="mt-8 text-center space-y-2">
          <p className="text-[0.625rem] tracking-[0.1em] uppercase text-slate-600">
            End-to-End Encrypted Clinical Records • Council Compliance Validated
          </p>
          <p className="text-[0.625rem] tracking-[0.05em] uppercase text-slate-700">
            © 2026 Sentinel AI Veterinary Diagnostics.
          </p>
        </footer>
      </main>
    </div>
  )
}
