import React, { useState, useEffect } from 'react'

export default function VetSettings() {
  const [profile, setProfile] = useState({
    fullName: localStorage.getItem("full_name") || localStorage.getItem("owner_name") || "Dr. Clinical Vet",
    email: localStorage.getItem("email") || "doctor@veterinary-council.gov",
    licenseNumber: localStorage.getItem("license_number") || "VET-LK-88902",
    phone: localStorage.getItem("phone") || "+94 77 123 4567",
    role: localStorage.getItem("role") || "vet"
  })
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [passwordState, setPasswordState] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState(false)

  const handleProfileSave = (e) => {
    e.preventDefault()
    localStorage.setItem("full_name", profile.fullName)
    localStorage.setItem("owner_name", profile.fullName)
    localStorage.setItem("license_number", profile.licenseNumber)
    localStorage.setItem("phone", profile.phone)
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 3000)
  }

  const handlePasswordChange = async (e) => {
    e.preventDefault()
    setPasswordError('')
    setPasswordSuccess(false)

    if (passwordState.newPassword.length < 4) {
      setPasswordError('New password must be at least 4 characters.')
      return
    }

    if (passwordState.newPassword !== passwordState.confirmPassword) {
      setPasswordError('New passwords do not match.')
      return
    }

    try {
      const token = localStorage.getItem("token")
      const response = await fetch("http://127.0.0.1:8000/api/user/change-password", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          current_password: passwordState.currentPassword,
          new_password: passwordState.newPassword
        })
      })

      if (response.ok) {
        setPasswordSuccess(true)
        setPasswordState({ currentPassword: '', newPassword: '', confirmPassword: '' })
      } else {
        const data = await response.json()
        setPasswordError(data.detail || 'Password update failed.')
      }
    } catch (err) {
      setPasswordError('Cannot reach server.')
    }
  }

  return (
    <div className="space-y-8 max-w-4xl animate-fadeIn">
      {/* Header */}
      <div className="pb-4 border-b border-outline-variant/10">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold uppercase tracking-wider">
            Practitioner Credentials
          </span>
        </div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
          Veterinary Profile &amp; Settings
        </h1>
        <p className="text-slate-400 text-xs md:text-sm mt-1">
          Manage your verified veterinary council credentials, clinical contact information, and authentication security.
        </p>
      </div>

      {/* Practitioner Info Card */}
      <section className="glass-card rounded-xl p-6 md:p-8 border border-white/5 space-y-6">
        <div className="flex items-center gap-4 pb-4 border-b border-white/5">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center shadow-glow-sm">
            <span className="material-symbols-outlined text-3xl">stethoscope</span>
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">{profile.fullName}</h2>
            <p className="text-xs text-emerald-400 font-mono mt-0.5">{profile.licenseNumber}</p>
            <span className="inline-block mt-1 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono font-bold">
              ROLE: VETERINARIAN AUTHORITY
            </span>
          </div>
        </div>

        {saveSuccess && (
          <div className="p-3.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded-lg text-xs font-bold flex items-center gap-2">
            <span className="material-symbols-outlined text-base">check_circle</span>
            Practitioner profile updated successfully.
          </div>
        )}

        <form onSubmit={handleProfileSave} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Full Name &amp; Title
              </label>
              <input
                value={profile.fullName}
                onChange={(e) => setProfile({ ...profile, fullName: e.target.value })}
                className="w-full bg-surface-container border border-outline-variant/20 rounded-lg p-3 text-xs text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
                type="text"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Clinical Email Address
              </label>
              <input
                value={profile.email}
                disabled
                className="w-full bg-surface-container-lowest border border-outline-variant/10 rounded-lg p-3 text-xs text-slate-500 cursor-not-allowed"
                type="email"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Veterinary License / Council Reg No.
              </label>
              <input
                value={profile.licenseNumber}
                onChange={(e) => setProfile({ ...profile, licenseNumber: e.target.value })}
                className="w-full bg-surface-container border border-outline-variant/20 rounded-lg p-3 text-xs text-on-surface focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                type="text"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Contact Phone Number
              </label>
              <input
                value={profile.phone}
                onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                className="w-full bg-surface-container border border-outline-variant/20 rounded-lg p-3 text-xs text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
                type="tel"
                required
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              className="px-5 py-2.5 bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-xs rounded-lg uppercase tracking-wider shadow-lg shadow-primary/20 hover:brightness-110 active:scale-95 transition-all"
            >
              Save Profile Details
            </button>
          </div>
        </form>
      </section>

      {/* Password Security Card */}
      <section className="glass-card rounded-xl p-6 md:p-8 border border-white/5 space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <span className="material-symbols-outlined text-emerald-400 text-lg">lock</span>
          Security &amp; Password
        </h2>

        {passwordError && (
          <div className="p-3.5 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold flex items-center gap-2">
            <span className="material-symbols-outlined text-base">warning</span>
            {passwordError}
          </div>
        )}

        {passwordSuccess && (
          <div className="p-3.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded-lg text-xs font-bold flex items-center gap-2">
            <span className="material-symbols-outlined text-base">check_circle</span>
            Password changed successfully.
          </div>
        )}

        <form onSubmit={handlePasswordChange} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">Current Password</label>
              <input
                value={passwordState.currentPassword}
                onChange={(e) => setPasswordState({ ...passwordState, currentPassword: e.target.value })}
                className="w-full bg-surface-container border border-outline-variant/20 rounded-lg p-3 text-xs text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
                type="password"
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">New Password</label>
              <input
                value={passwordState.newPassword}
                onChange={(e) => setPasswordState({ ...passwordState, newPassword: e.target.value })}
                className="w-full bg-surface-container border border-outline-variant/20 rounded-lg p-3 text-xs text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
                type="password"
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">Confirm New Password</label>
              <input
                value={passwordState.confirmPassword}
                onChange={(e) => setPasswordState({ ...passwordState, confirmPassword: e.target.value })}
                className="w-full bg-surface-container border border-outline-variant/20 rounded-lg p-3 text-xs text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
                type="password"
                required
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              className="px-5 py-2.5 bg-surface-container-highest text-white hover:text-emerald-400 font-bold text-xs rounded-lg uppercase tracking-wider border border-white/10 hover:border-emerald-500/30 transition-all"
            >
              Update Password
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
