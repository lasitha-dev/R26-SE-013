import React from 'react'
import { useNavigate } from 'react-router-dom'

export default function VetRegistrationSuccess() {
  const navigate = useNavigate()

  return (
    <div className="bg-background min-h-screen flex items-center justify-center p-6 selection:bg-primary/30 selection:text-primary text-on-surface">
      <main className="w-full max-w-xl">
        <div className="bg-surface-container rounded-xl border border-primary-container/20 overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
          <div className="p-8 md:p-12 flex flex-col items-center text-center">
            <div className="flex flex-col items-center mb-8">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center text-primary">
                  <span
                    className="material-symbols-outlined text-2xl text-primary"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    medical_services
                  </span>
                </div>
                <span className="text-2xl font-extrabold tracking-tighter text-on-surface">ADRS CORE</span>
              </div>
              <span className="text-[10px] uppercase tracking-[0.2em] font-semibold text-tertiary mt-2 opacity-60">
                CLINICAL VETERINARY PORTAL
              </span>
            </div>

            <div className="relative mb-8">
              <div className="absolute inset-0 bg-primary/20 blur-3xl rounded-full scale-150"></div>
              <div className="relative bg-surface-container-high p-6 rounded-full border border-primary/30 shadow-[0_0_20px_rgba(78,222,163,0.15)]">
                <span
                  className="material-symbols-outlined text-6xl text-primary leading-none"
                  style={{ fontVariationSettings: "'wght' 600" }}
                >
                  verified
                </span>
              </div>
            </div>

            <h1 className="text-3xl font-bold text-on-surface mb-3 tracking-tight">
              Veterinarian Account Created
            </h1>
            <p className="text-on-surface-variant leading-relaxed max-w-sm mb-10 text-sm">
              Your clinical practitioner credentials have been authorized. You can now access the AI Diagnostics Workbench and assigned herd health telemetry.
            </p>

            <div className="w-full space-y-4 mb-8">
              <button
                onClick={() => navigate('/health/vet-login')}
                className="w-full py-4 px-6 bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold rounded-lg flex items-center justify-center gap-2 hover:opacity-90 transition-all active:scale-[0.98] uppercase text-sm tracking-wider shadow-lg shadow-primary/20"
                type="button"
              >
                <span className="material-symbols-outlined text-xl">login</span>
                Proceed to Vet Login
              </button>
              <button
                onClick={() => navigate('/vet/dashboard')}
                className="w-full py-4 px-6 bg-surface-container-highest/40 text-primary border border-primary/20 font-semibold rounded-lg hover:bg-surface-container-highest transition-all active:scale-[0.98] flex items-center justify-center gap-2 text-sm"
                type="button"
              >
                <span className="material-symbols-outlined text-xl">dashboard</span>
                Access Clinical Dashboard
              </button>
            </div>

            <div className="pt-6 border-t border-outline-variant/10 w-full">
              <div className="flex items-center justify-center gap-2 text-tertiary/60 text-sm">
                <span className="material-symbols-outlined text-lg">shield</span>
                <p>Council Registration Number Recorded &amp; Verified.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 flex justify-center items-center gap-6 opacity-40">
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface">
              Clinical Telemetry: Active
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface">
              Role: Veterinarian Authority
            </span>
          </div>
        </div>
      </main>
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/5 blur-[120px] rounded-full pointer-events-none -z-10"></div>
    </div>
  )
}
