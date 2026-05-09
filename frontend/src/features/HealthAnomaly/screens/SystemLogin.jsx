import React from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function SystemLogin() {
  const navigate = useNavigate()

  return (
    <div className="flex items-center justify-center min-h-screen p-6 overflow-hidden bg-surface text-on-surface">
      <main className="w-full max-w-md">
        <div className="absolute inset-0 z-[-1] pointer-events-none opacity-20">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary/20 blur-[120px]"></div>
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-secondary/10 blur-[120px]"></div>
        </div>

        <div className="relative">
          <div className="flex flex-col items-center mb-10">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-12 h-12 flex items-center justify-center rounded-lg bg-primary-container/20 text-primary">
                <span
                  className="material-symbols-outlined text-3xl"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  shield
                </span>
              </div>
              <span className="text-2xl font-black tracking-tighter text-on-surface uppercase">ADRS Core</span>
            </div>
            <p className="text-[0.6875rem] tracking-[0.15em] uppercase text-slate-500 font-bold">
              Sentinel AI Veterinary Diagnostics
            </p>
          </div>

          <section className="bg-surface-container-high rounded-lg p-10 shadow-2xl shadow-black/50 border border-outline-variant/10">
            <div className="mb-8">
              <h1 className="text-2xl font-bold tracking-tight text-on-surface">System Login</h1>
              <p className="text-sm text-slate-400 mt-2">Authorized clinical access only.</p>
            </div>
            <form
              className="space-y-6"
              onSubmit={(e) => {
                e.preventDefault()
                navigate('/health/dashboard')
              }}
            >
              <div className="space-y-2">
                <label
                  className="text-[0.6875rem] font-bold tracking-[0.05em] uppercase text-slate-400"
                  htmlFor="email"
                >
                  Email Address
                </label>
                <div className="relative group">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-500 group-focus-within:text-primary transition-colors">
                    alternate_email
                  </span>
                  <input
                    className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded py-3.5 pl-12 pr-4 text-on-surface placeholder:text-slate-600 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/20 transition-all"
                    id="email"
                    name="email"
                    placeholder="clinician@sentinel.ai"
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
                    className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded py-3.5 pl-12 pr-4 text-on-surface placeholder:text-slate-600 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/20 transition-all"
                    id="password"
                    name="password"
                    placeholder="••••••••"
                    type="password"
                  />
                </div>
              </div>

              <button
                className="w-full bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold py-4 rounded shadow-lg shadow-primary/10 hover:opacity-90 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
                type="submit"
              >
                <span className="material-symbols-outlined text-xl">login</span>
                Secure Login
              </button>
            </form>

            <div className="mt-8 flex items-center justify-center gap-3">
              <div className="h-[1px] flex-grow bg-outline-variant/10"></div>
              <span className="text-[0.625rem] text-slate-500 uppercase tracking-widest whitespace-nowrap">
                Clinical Network Status: Active
              </span>
              <div className="h-[1px] flex-grow bg-outline-variant/10"></div>
            </div>

            <div className="mt-8 text-center">
              <p className="text-sm text-slate-500">
                New to Sentinel network?
                <Link
                  className="text-secondary font-bold hover:underline underline-offset-4 ml-1 transition-all"
                  to="/health/registration"
                >
                  Register Farm
                </Link>
              </p>
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

        <footer className="mt-12 text-center space-y-2">
          <p className="text-[0.625rem] tracking-[0.1em] uppercase text-slate-600">
            End-to-End Encryption Enabled • Precision Engineered Intelligence
          </p>
          <p className="text-[0.625rem] tracking-[0.05em] uppercase text-slate-700">
            © 2024 Sentinel AI Veterinary Diagnostics.
          </p>
        </footer>
      </main>
    </div>
  )
}
