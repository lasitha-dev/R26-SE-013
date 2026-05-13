import React from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function PasswordReset() {
  const navigate = useNavigate()

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col items-center p-6">
      <div className="mb-10 text-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-16 h-16 bg-primary-container rounded-lg flex items-center justify-center shadow-lg shadow-primary-container/20">
            <span
              className="material-symbols-outlined text-on-primary text-4xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              shield
            </span>
          </div>
          <div>
            <h1 className="text-2xl font-extrabold tracking-tighter text-on-surface">ADRS CORE</h1>
            <p className="text-[0.6875rem] uppercase tracking-[0.2em] font-semibold text-primary">Clinical Precision</p>
          </div>
        </div>
      </div>

      <main className="w-full max-w-md flex-grow flex flex-col justify-center items-center">
        <div className="glass-card border border-outline-variant/20 rounded-xl p-8 shadow-2xl w-full">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-on-surface mb-2">Reset Password</h2>
            <p className="text-sm text-on-surface-variant leading-relaxed">
              Enter your email address below and we&apos;ll send you a link to reset your password.
            </p>
          </div>

          <form
            className="space-y-6"
            onSubmit={(e) => {
              e.preventDefault()
              navigate('/health/login')
            }}
          >
            <div className="space-y-2">
              <label
                className="block text-[0.6875rem] uppercase tracking-wider font-bold text-on-surface-variant"
                htmlFor="email"
              >
                Email Address
              </label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-xl">
                  mail
                </span>
                <input
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 pl-11 pr-4 text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all duration-200"
                  id="email"
                  name="email"
                  placeholder="e.g., clinician@sentinel-ai.vet"
                  required
                  type="email"
                />
              </div>
            </div>

            <button
              className="w-full bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold py-3.5 rounded-lg shadow-lg shadow-primary/10 hover:brightness-110 active:scale-[0.98] transition-all duration-200 text-sm tracking-wide"
              type="submit"
            >
              Send Reset Link
            </button>
          </form>

          <div className="mt-8 text-center">
            <Link
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-secondary transition-colors duration-200"
              to="/health/login"
            >
              <span className="material-symbols-outlined text-lg">arrow_back</span>
              Back to Login
            </Link>
          </div>
        </div>

        <div className="mt-8 flex flex-col items-center gap-4">
          <div className="flex items-center gap-2 bg-surface-container-low px-3 py-1 rounded-full border border-outline-variant/10">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
            </span>
            <span className="text-[0.625rem] font-bold uppercase tracking-widest text-on-surface-variant">
              System Online
            </span>
          </div>
        </div>
      </main>

      <div className="fixed top-0 left-0 w-full h-full -z-10 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-primary/5 blur-[120px]"></div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary-container/5 blur-[120px]"></div>
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] opacity-[0.03] mix-blend-overlay"></div>
      </div>
    </div>
  )
}
