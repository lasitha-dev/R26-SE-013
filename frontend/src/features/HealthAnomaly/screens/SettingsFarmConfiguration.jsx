import React, { useState, useEffect, useContext } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ProfileContext } from '../../../context/ProfileContext.jsx'

export default function SettingsFarmConfiguration() {
  const navigate = useNavigate()
  const { setProfilePhoto, setFarmerName } = useContext(ProfileContext)


  const [activeTab, setActiveTab] = useState('account') // 'account', 'security', 'notifications', 'system'
  
  // Account state
  const [profile, setProfile] = useState({
    owner_name: '',
    email: '',
    location_district: '',
    registration_number: '',
    veterinarian_name: '',
    profile_photo: ''
  })
  
  // Form messages
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  // Notifications state toggles
  const [emailAlerts, setEmailAlerts] = useState(true)
  const [pushAlerts, setPushAlerts] = useState(true)
  const [thiThreshold, setThiThreshold] = useState(78)
  const [milkDropThreshold, setMilkDropThreshold] = useState(2.0)

  // System state toggles
  const [cloudSync, setCloudSync] = useState(true)
  const [visionDiagnostics, setVisionDiagnostics] = useState(true)

  const fetchProfile = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('http://127.0.0.1:8000/api/user/profile', {
        headers: {
          Authorization: token ? `Bearer ${token}` : ''
        }
      })
      if (response.ok) {
        const data = await response.json()
        setProfile({
          owner_name: data.owner_name || '',
          email: data.email || '',
          location_district: data.location_district || '',
          registration_number: data.registration_number || '',
          veterinarian_name: data.veterinarian_name || '',
          profile_photo: data.profile_photo || ''
        })
        if (data.profile_photo) {
          setProfilePhoto(data.profile_photo)
        }
        if (data.owner_name) {
          setFarmerName(data.owner_name)
        }
      }
    } catch (err) {
      console.error('Error fetching user profile:', err)
    }
  }

  // Breed Defaults State overrides
  const [selectedBreed, setSelectedBreed] = useState('Holstein-Friesian')
  const [breedAvgMilk, setBreedAvgMilk] = useState('')
  const [breedAvgWeight, setBreedAvgWeight] = useState('')
  const [breedSettingsList, setBreedSettingsList] = useState([])

  const fetchBreedSettings = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('http://127.0.0.1:8000/api/user/breed-settings', {
        headers: { Authorization: token ? `Bearer ${token}` : '' }
      })
      if (response.ok) {
        const data = await response.json()
        setBreedSettingsList(data || [])
      }
    } catch (err) {
      console.error('Error fetching breed settings:', err)
    }
  }

  const breedDefaults = {
    'Holstein-Friesian': { milk: '25.0', weight: '600.0' },
    'Jersey': { milk: '18.0', weight: '450.0' },
    'Ayrshire': { milk: '20.0', weight: '500.0' },
    'Brown_Swiss': { milk: '22.0', weight: '580.0' },
    'Sahiwal': { milk: '12.0', weight: '420.0' },
    'Gir': { milk: '14.0', weight: '400.0' },
    'Exotic_Local_Cross': { milk: '10.0', weight: '350.0' },
    'Boran': { milk: '8.0', weight: '380.0' },
    'Ankole': { milk: '6.0', weight: '450.0' }
  }

  useEffect(() => {
    // Sync inputs when selected breed changes: fetch database overrides or fall back to system defaults
    const match = breedSettingsList.find(b => b.breed === selectedBreed)
    if (match) {
      setBreedAvgMilk(match.avg_milk !== null ? match.avg_milk.toString() : breedDefaults[selectedBreed]?.milk || '')
      setBreedAvgWeight(match.avg_weight !== null ? match.avg_weight.toString() : breedDefaults[selectedBreed]?.weight || '')
    } else {
      const defaults = breedDefaults[selectedBreed] || { milk: '', weight: '' }
      setBreedAvgMilk(defaults.milk)
      setBreedAvgWeight(defaults.weight)
    }
  }, [selectedBreed, breedSettingsList])

  const handleSaveBreedSettings = async (e) => {
    e.preventDefault()
    setErrorMessage('')
    setSuccessMessage('')
    setLoading(true)
    
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('http://127.0.0.1:8000/api/user/breed-settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          breed: selectedBreed,
          avg_milk: breedAvgMilk !== '' ? parseFloat(breedAvgMilk) : null,
          avg_weight: breedAvgWeight !== '' ? parseFloat(breedAvgWeight) : null
        })
      })
      
      if (response.ok) {
        setSuccessMessage(`Breed defaults for ${selectedBreed} saved successfully.`)
        await fetchBreedSettings()
      } else {
        const data = await response.json()
        setErrorMessage(data.detail || 'Failed to save breed settings.')
      }
    } catch (err) {
      setErrorMessage('Cannot connect to server.')
    } finally {
      setLoading(false)
    }
  }

  const handleResetBreedSettings = async () => {
    setErrorMessage('')
    setSuccessMessage('')
    setLoading(true)
    
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`http://127.0.0.1:8000/api/user/breed-settings/${selectedBreed}`, {
        method: 'DELETE',
        headers: {
          Authorization: token ? `Bearer ${token}` : ''
        }
      })
      
      if (response.ok) {
        setSuccessMessage(`Defaults for ${selectedBreed} reset to system configuration.`)
        const defaults = breedDefaults[selectedBreed] || { milk: '', weight: '' }
        setBreedAvgMilk(defaults.milk)
        setBreedAvgWeight(defaults.weight)
        await fetchBreedSettings()
      } else {
        const data = await response.json()
        setErrorMessage(data.detail || 'Failed to reset breed defaults.')
      }
    } catch (err) {
      setErrorMessage('Cannot connect to server.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProfile()
    fetchBreedSettings()
  }, [])


  const handleAccountSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage('')
    setSuccessMessage('')
    setLoading(true)

    try {
      const token = localStorage.getItem('token')
      const response = await fetch('http://127.0.0.1:8000/api/user/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          owner_name: profile.owner_name,
          veterinarian_name: profile.veterinarian_name,
          profile_photo: profile.profile_photo
        })
      })

      if (response.ok) {
        setSuccessMessage('Farmer profile details updated successfully.')
        setProfilePhoto(profile.profile_photo)
        setFarmerName(profile.owner_name)
        fetchProfile()
      } else {

        const data = await response.json()
        setErrorMessage(data.detail || 'Failed to update profile details.')
      }
    } catch (err) {
      setErrorMessage('Network error. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }



  const handleSecuritySubmit = async (e) => {
    e.preventDefault()
    setErrorMessage('')
    setSuccessMessage('')

    const formData = new FormData(e.target)
    const currentPassword = formData.get('current_password')
    const newPassword = formData.get('new_password')
    const confirmNewPassword = formData.get('confirm_new_password')

    if (!currentPassword || !newPassword || !confirmNewPassword) {
      setErrorMessage('Please fill in all security fields.')
      return
    }

    if (newPassword !== confirmNewPassword) {
      setErrorMessage('New passwords do not match. Please re-enter.')
      return
    }

    if (newPassword.length < 4) {
      setErrorMessage('New password must be at least 4 characters long.')
      return
    }

    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('http://127.0.0.1:8000/api/user/change-password', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      })

      if (response.ok) {
        setSuccessMessage('Security password reset successfully.')
        e.target.reset()
      } else {
        const data = await response.json()
        setErrorMessage(data.detail || 'Password change failed.')
      }
    } catch (err) {
      setErrorMessage('Network error. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  const handlePhotoUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return

    const reader = new FileReader()
    reader.readAsDataURL(file)
    reader.onload = (event) => {
      const img = new Image()
      img.src = event.target.result
      img.onload = () => {
        const canvas = document.createElement('canvas')
        let width = img.width
        let height = img.height
        const MAX_SIZE = 800

        if (width > height) {
          if (width > MAX_SIZE) {
            height = Math.round((height * MAX_SIZE) / width)
            width = MAX_SIZE
          }
        } else {
          if (height > MAX_SIZE) {
            width = Math.round((width * MAX_SIZE) / height)
            height = MAX_SIZE
          }
        }

        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, width, height)

        const compressed = canvas.toDataURL('image/jpeg', 0.9)
        setProfile((prev) => ({ ...prev, profile_photo: compressed }))
      }
    }
  }



  return (
    <div className="space-y-8">
      {/* Header Bar */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <Link
            to="/health/dashboard"
            className="flex items-center gap-1 text-primary-fixed uppercase text-[10px] font-black tracking-[0.3em] hover:underline"
          >
            <span className="material-symbols-outlined text-xs">arrow_back</span>
            Back to Dashboard
          </Link>
          <div className="h-px w-12 bg-outline-variant/30"></div>
        </div>
        <h2 className="text-4xl font-extrabold tracking-tight text-on-surface mt-2 mb-2 font-headline uppercase">
          SYSTEM CONFIGURATION <span className="text-primary">&amp;</span> SETTINGS
        </h2>
        <div className="h-1 w-24 bg-primary rounded-full mt-1"></div>
      </div>

      {/* Main Settings Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Side Sidebar Menu */}
        <div className="lg:col-span-3 space-y-2">
          {[
            { id: 'account', label: 'Farmer Profile', icon: 'person' },
            { id: 'security', label: 'Security & Access', icon: 'security' },
            { id: 'notifications', label: 'Notifications', icon: 'notifications' },
            { id: 'system', label: 'System Configuration', icon: 'settings_suggest' },
            { id: 'breed', label: 'Breed Defaults', icon: 'pets' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id)
                setErrorMessage('')
                setSuccessMessage('')
              }}
              className={`w-full flex items-center gap-3 px-5 py-4 rounded-xl font-bold text-sm uppercase tracking-wider transition-all border ${
                activeTab === tab.id
                  ? 'bg-primary/10 text-primary border-primary/20'
                  : 'bg-surface-container-low hover:bg-surface-container-high text-slate-400 border-white/5'
              }`}
              type="button"
            >
              <span className="material-symbols-outlined">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Right Side Settings Panel Forms */}
        <div className="lg:col-span-9 bg-surface-container-low rounded-2xl p-6 md:p-10 border border-white/5 relative overflow-hidden">
          {errorMessage && (
            <div className="mb-6 p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider">
              {errorMessage}
            </div>
          )}

          {successMessage && (
            <div className="mb-6 p-4 bg-primary/10 border border-primary/20 text-primary rounded-lg text-xs font-bold uppercase tracking-wider">
              {successMessage}
            </div>
          )}

          {/* Account/Profile Form Tab */}
          {activeTab === 'account' && (
            <form onSubmit={handleAccountSubmit} className="space-y-6">
              <div className="flex flex-col items-center sm:flex-row gap-6 pb-6 border-b border-white/5">
                {/* Farmer Photo Avatar Uploader */}
                <div className="relative group cursor-pointer w-24 h-24 rounded-full overflow-hidden border-2 border-primary/25 bg-surface-container-lowest flex items-center justify-center flex-shrink-0">
                  {profile.profile_photo ? (
                    <img
                      alt="Farmer Avatar"
                      className="w-full h-full object-cover"
                      src={profile.profile_photo}
                    />
                  ) : (
                    <span className="material-symbols-outlined text-4xl text-slate-500">
                      account_circle
                    </span>
                  )}
                  <input
                    accept="image/*"
                    className="hidden"
                    id="profile-avatar-uploader"
                    onChange={handlePhotoUpload}
                    type="file"
                  />
                  <label
                    htmlFor="profile-avatar-uploader"
                    className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center cursor-pointer text-white text-[9px] font-bold uppercase tracking-widest"
                  >
                    <span className="material-symbols-outlined text-base">photo_camera</span>
                    Change
                  </label>
                </div>
                <div className="space-y-1 text-center sm:text-left">
                  <h4 className="text-lg font-bold text-white uppercase tracking-tight">Farmer Profile Photo</h4>
                  <p className="text-xs text-slate-400">Click on avatar to select or upload a custom image file.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                    Owner Full Name
                  </label>
                  <input
                    value={profile.owner_name}
                    onChange={(e) => setProfile({ ...profile, owner_name: e.target.value })}
                    className="w-full bg-surface-container-lowest border border-white/5 rounded-lg px-4 py-3 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary outline-none transition-all"
                    required
                    type="text"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                    Veterinarian Contact Name
                  </label>
                  <input
                    value={profile.veterinarian_name}
                    onChange={(e) => setProfile({ ...profile, veterinarian_name: e.target.value })}
                    className="w-full bg-surface-container-lowest border border-white/5 rounded-lg px-4 py-3 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary outline-none transition-all"
                    required
                    type="text"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-450 uppercase tracking-widest">
                    Email Address (Disabled)
                  </label>
                  <input
                    value={profile.email}
                    disabled
                    className="w-full bg-surface-container-lowest/50 border border-white/5 rounded-lg px-4 py-3 text-sm text-slate-500 cursor-not-allowed outline-none"
                    type="email"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-455 uppercase tracking-widest">
                    Farm Location District (Disabled)
                  </label>
                  <input
                    value={profile.location_district}
                    disabled
                    className="w-full bg-surface-container-lowest/50 border border-white/5 rounded-lg px-4 py-3 text-sm text-slate-500 cursor-not-allowed outline-none"
                    type="text"
                  />
                </div>
              </div>

              <div className="pt-4 flex justify-end">
                <button
                  className="px-8 py-3.5 bg-primary text-on-primary font-black text-xs uppercase tracking-wider rounded-lg transition-all active:scale-95 disabled:opacity-50"
                  type="submit"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Save Profile Details'}
                </button>
              </div>
            </form>
          )}

          {/* Security / Password Reset Tab */}
          {activeTab === 'security' && (
            <form onSubmit={handleSecuritySubmit} className="space-y-6">
              <div className="space-y-1 pb-4 border-b border-white/5">
                <h4 className="text-base font-bold text-white uppercase tracking-tight">Reset Password Access</h4>
                <p className="text-xs text-slate-400">Change password to ensure account security and privacy protection.</p>
              </div>

              <div className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                    Current Password
                  </label>
                  <input
                    className="w-full bg-surface-container-lowest border border-white/5 rounded-lg px-4 py-3 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary outline-none transition-all"
                    name="current_password"
                    required
                    type="password"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      New Password
                    </label>
                    <input
                      className="w-full bg-surface-container-lowest border border-white/5 rounded-lg px-4 py-3 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary outline-none transition-all"
                      name="new_password"
                      required
                      type="password"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      Confirm New Password
                    </label>
                    <input
                      className="w-full bg-surface-container-lowest border border-white/5 rounded-lg px-4 py-3 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary outline-none transition-all"
                      name="confirm_new_password"
                      required
                      type="password"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 flex justify-end">
                <button
                  className="px-8 py-3.5 bg-primary text-on-primary font-black text-xs uppercase tracking-wider rounded-lg transition-all active:scale-95 disabled:opacity-50"
                  type="submit"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Update Password'}
                </button>
              </div>
            </form>
          )}

          {/* Notifications Tab */}
          {activeTab === 'notifications' && (
            <div className="space-y-8">
              <div className="space-y-1 pb-4 border-b border-white/5">
                <h4 className="text-base font-bold text-white uppercase tracking-tight">Notification Channels</h4>
                <p className="text-xs text-slate-400">Manage communication methods for AI diagnostics and alerts.</p>
              </div>

              <div className="space-y-6">
                <div className="flex items-center justify-between p-4 bg-surface-container-lowest/30 rounded-xl border border-white/5">
                  <div>
                    <h5 className="text-sm font-bold text-white">Email Daily Briefings</h5>
                    <p className="text-xs text-slate-500 mt-0.5">Send daily animal health digests to owner and veterinarian.</p>
                  </div>
                  <button
                    onClick={() => setEmailAlerts(!emailAlerts)}
                    className={`w-12 h-6 rounded-full relative transition-colors duration-300 ${
                      emailAlerts ? 'bg-primary' : 'bg-surface-container-highest'
                    }`}
                    type="button"
                  >
                    <span
                      className={`absolute top-1 w-4 h-4 rounded-full shadow-md transition-all ${
                        emailAlerts ? 'right-1 bg-on-primary' : 'left-1 bg-slate-500'
                      }`}
                    ></span>
                  </button>
                </div>

                <div className="flex items-center justify-between p-4 bg-surface-container-lowest/30 rounded-xl border border-white/5">
                  <div>
                    <h5 className="text-sm font-bold text-white">Heat Stress Warning Push Alerts</h5>
                    <p className="text-xs text-slate-500 mt-0.5">Instant notification when THI indexes enter critical range.</p>
                  </div>
                  <button
                    onClick={() => setPushAlerts(!pushAlerts)}
                    className={`w-12 h-6 rounded-full relative transition-colors duration-300 ${
                      pushAlerts ? 'bg-primary' : 'bg-surface-container-highest'
                    }`}
                    type="button"
                  >
                    <span
                      className={`absolute top-1 w-4 h-4 rounded-full shadow-md transition-all ${
                        pushAlerts ? 'right-1 bg-on-primary' : 'left-1 bg-slate-500'
                      }`}
                    ></span>
                  </button>
                </div>

                {/* Heat Stress THI Alert Level Slider */}
                <div className="p-4 bg-surface-container-lowest/30 rounded-xl border border-white/5 space-y-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <h5 className="text-sm font-bold text-white">Critical THI Warning Level</h5>
                      <p className="text-xs text-slate-500 mt-0.5">Define warning trigger point for heat stress index.</p>
                    </div>
                    <span className="text-primary font-black text-xl font-display">{thiThreshold}</span>
                  </div>
                  <input
                    className="w-full h-1.5 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary"
                    min="60"
                    max="90"
                    value={thiThreshold}
                    onChange={(e) => setThiThreshold(parseInt(e.target.value))}
                    type="range"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-bold">
                    <span>60 (LOW RISK)</span>
                    <span>90 (SEVERE ANOMALY STRESS)</span>
                  </div>
                </div>

                {/* Daily Milk Drop Threshold warning */}
                <div className="p-4 bg-surface-container-lowest/30 rounded-xl border border-white/5 space-y-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <h5 className="text-sm font-bold text-white">Daily Milk Drop Warning Limit</h5>
                      <p className="text-xs text-slate-500 mt-0.5">Triggers warning alert if daily yield drop exceeds this margin.</p>
                    </div>
                    <span className="text-primary font-black text-xl font-display">{milkDropThreshold} L</span>
                  </div>
                  <input
                    className="w-full h-1.5 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary"
                    min="0.5"
                    max="5.0"
                    step="0.1"
                    value={milkDropThreshold}
                    onChange={(e) => setMilkDropThreshold(parseFloat(e.target.value))}
                    type="range"
                  />
                </div>
              </div>
            </div>
          )}

          {/* System Tab */}
          {activeTab === 'system' && (
            <div className="space-y-8">
              <div className="space-y-1 pb-4 border-b border-white/5">
                <h4 className="text-base font-bold text-white uppercase tracking-tight">System Configuration</h4>
                <p className="text-xs text-slate-400">Configure global parameters and backup features.</p>
              </div>

              <div className="space-y-6">
                <div className="flex items-center justify-between p-4 bg-surface-container-lowest/30 rounded-xl border border-white/5">
                  <div>
                    <h5 className="text-sm font-bold text-white">Automated Cloud Sync Backup</h5>
                    <p className="text-xs text-slate-500 mt-0.5">Encrypt and synchronize farm data automatically.</p>
                  </div>
                  <button
                    onClick={() => setCloudSync(!cloudSync)}
                    className={`w-12 h-6 rounded-full relative transition-colors duration-300 ${
                      cloudSync ? 'bg-primary' : 'bg-surface-container-highest'
                    }`}
                    type="button"
                  >
                    <span
                      className={`absolute top-1 w-4 h-4 rounded-full shadow-md transition-all ${
                        cloudSync ? 'right-1 bg-on-primary' : 'left-1 bg-slate-500'
                      }`}
                    ></span>
                  </button>
                </div>

                <div className="flex items-center justify-between p-4 bg-surface-container-lowest/30 rounded-xl border border-white/5">
                  <div>
                    <h5 className="text-sm font-bold text-white">AI Vision Diagnostics</h5>
                    <p className="text-xs text-slate-500 mt-0.5">Activate real-time image scan anomaly analysis features.</p>
                  </div>
                  <button
                    onClick={() => setVisionDiagnostics(!visionDiagnostics)}
                    className={`w-12 h-6 rounded-full relative transition-colors duration-300 ${
                      visionDiagnostics ? 'bg-primary' : 'bg-surface-container-highest'
                    }`}
                    type="button"
                  >
                    <span
                      className={`absolute top-1 w-4 h-4 rounded-full shadow-md transition-all ${
                        visionDiagnostics ? 'right-1 bg-on-primary' : 'left-1 bg-slate-500'
                      }`}
                    ></span>
                  </button>
                </div>

                {/* Cloud Sync Status info */}
                <div className="bg-surface-container-lowest/50 p-6 rounded-xl border border-outline-variant/10">
                  <div className="flex items-center gap-4">
                    <div className="bg-primary/10 p-3 rounded-full">
                      <span
                        className="material-symbols-outlined text-primary"
                        style={{ fontVariationSettings: "'FILL' 1" }}
                      >
                        cloud_done
                      </span>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">
                        Cloud Sync Backup: <span className="text-primary">ACTIVE</span>
                      </p>
                      <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-wider">Last backup synchronization: 1 minute ago</p>
                    </div>
                  </div>
                  <div className="mt-6 h-1 w-full bg-surface-container-highest rounded-full overflow-hidden">
                    <div className="h-full bg-primary w-full shadow-[0_0_10px_rgba(78,222,163,0.5)]"></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          {/* Breed Settings Tab */}
          {activeTab === 'breed' && (
            <div className="space-y-8">
              <div className="space-y-1 pb-4 border-b border-white/5">
                <h4 className="text-base font-bold text-white uppercase tracking-tight">Breed Settings & Defaults</h4>
                <p className="text-xs text-slate-400">Configure global average metrics per bovine breed for ML anomaly thresholds.</p>
              </div>

              <form onSubmit={handleSaveBreedSettings} className="space-y-6">
                {/* Select Breed */}
                <div className="space-y-2">
                  <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                    Select Breed
                  </label>
                  <div className="relative">
                    <select
                      className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                      value={selectedBreed}
                      onChange={(e) => setSelectedBreed(e.target.value)}
                      required
                    >
                      <option value="Holstein-Friesian">Holstein-Friesian</option>
                      <option value="Jersey">Jersey</option>
                      <option value="Ayrshire">Ayrshire</option>
                      <option value="Brown_Swiss">Brown_Swiss</option>
                      <option value="Sahiwal">Sahiwal</option>
                      <option value="Gir">Gir</option>
                      <option value="Exotic_Local_Cross">Exotic_Local_Cross</option>
                      <option value="Boran">Boran</option>
                      <option value="Ankole">Ankole</option>
                    </select>
                    <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                      expand_more
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Override Avg Milk */}
                  <div className="space-y-2">
                    <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                      Override Breed Avg Milk (L)
                    </label>
                    <div className="relative">
                      <input
                        className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3.5 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                        placeholder="System default (e.g. 25.0)"
                        value={breedAvgMilk}
                        onChange={(e) => setBreedAvgMilk(e.target.value)}
                        type="number"
                        step="0.1"
                        min="0"
                      />
                    </div>
                  </div>

                  {/* Override Avg Weight */}
                  <div className="space-y-2">
                    <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                      Override Breed Avg Weight (kg)
                    </label>
                    <div className="relative">
                      <input
                        className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3.5 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                        placeholder="System default (e.g. 600.0)"
                        value={breedAvgWeight}
                        onChange={(e) => setBreedAvgWeight(e.target.value)}
                        type="number"
                        step="0.01"
                        min="0.1"
                      />
                    </div>
                  </div>
                </div>

                <div className="pt-6 flex flex-col sm:flex-row gap-4 items-center justify-between">
                  <button
                    onClick={handleResetBreedSettings}
                    className="w-full sm:w-auto px-6 py-3 bg-error/10 hover:bg-error/20 text-error text-xs font-bold uppercase rounded-lg border border-error/25 transition-all"
                    type="button"
                    disabled={loading}
                  >
                    Reset to Default
                  </button>
                  <button
                    className="w-full sm:w-auto px-8 py-3 bg-primary hover:opacity-90 text-on-primary font-black text-xs uppercase tracking-wider rounded-lg transition-all"
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? 'Saving...' : 'Save Settings'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
