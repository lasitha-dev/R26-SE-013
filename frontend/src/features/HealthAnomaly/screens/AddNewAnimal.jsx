import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export const sriLankanBreeds = [
  "Holstein-Friesian", "Jersey", "Ayrshire", "Brown_Swiss", "Guernsey", 
  "Fleckvieh", "Simmental", "Milking_Shorthorn", "Illawarra_Shorthorn",
  "Sahiwal", "Red_Sindhi", "Gir", "Tharparkar", "Hariana", "Kankrej", "Ongole",
  "Australian_Friesian_Sahiwal", "Australian_Milking_Zebu",
  "Holstein_Zebu_Cross", "Jersey_Zebu_Cross", "Exotic_Local_Cross"
];

export const allBreeds = [
  { value: "Africander", label: "Africander" },
  { value: "Ankole", label: "Ankole" },
  { value: "Australian_Friesian_Sahiwal", label: "Australian Friesian Sahiwal" },
  { value: "Australian_Milking_Zebu", label: "Australian Milking Zebu" },
  { value: "Ayrshire", label: "Ayrshire" },
  { value: "Boran", label: "Boran" },
  { value: "Brown_Swiss", label: "Brown Swiss" },
  { value: "Butana", label: "Butana" },
  { value: "Danish_Red", label: "Danish Red" },
  { value: "Deoni", label: "Deoni" },
  { value: "Exotic_Local_Cross", label: "Exotic Local Cross" },
  { value: "Fleckvieh", label: "Fleckvieh" },
  { value: "Gangatiri", label: "Gangatiri" },
  { value: "Gir", label: "Gir" },
  { value: "Girolando", label: "Girolando" },
  { value: "Guernsey", label: "Guernsey" },
  { value: "Hariana", label: "Hariana" },
  { value: "Holstein-Friesian", label: "Holstein-Friesian" },
  { value: "Holstein_Zebu_Cross", label: "Holstein Zebu Cross" },
  { value: "Illawarra_Shorthorn", label: "Illawarra Shorthorn" },
  { value: "Jersey", label: "Jersey" },
  { value: "Jersey_Zebu_Cross", label: "Jersey Zebu Cross" },
  { value: "Kankrej", label: "Kankrej" },
  { value: "Kenana", label: "Kenana" },
  { value: "Krishna_Valley", label: "Krishna Valley" },
  { value: "Milking_Shorthorn", label: "Milking Shorthorn" },
  { value: "Montbeliarde", label: "Montbeliarde" },
  { value: "NDama", label: "NDama" },
  { value: "Normande", label: "Normande" },
  { value: "Norwegian_Red", label: "Norwegian Red" },
  { value: "Ongole", label: "Ongole" },
  { value: "Rathi", label: "Rathi" },
  { value: "Red_Poll_Africa", label: "Red Poll Africa" },
  { value: "Red_Sindhi", label: "Red Sindhi" },
  { value: "Sahiwal", label: "Sahiwal" },
  { value: "Simmental", label: "Simmental" },
  { value: "Tharparkar", label: "Tharparkar" },
  { value: "Tipo_Carora", label: "Tipo Carora" },
  { value: "White_Fulani", label: "White Fulani" },
  { value: "Zebu_Cross_Brazil", label: "Zebu Cross Brazil" }
];

// Dynamic Age Calculation helper function
export const calculateAge = (dobString) => {
  if (!dobString) return 'N/A'
  const dob = new Date(dobString)
  const today = new Date()

  // Reset hours to compare only dates
  dob.setHours(0, 0, 0, 0)
  today.setHours(0, 0, 0, 0)

  if (dob > today) {
    return 'Not Born Yet'
  }

  let years = today.getFullYear() - dob.getFullYear()
  let months = today.getMonth() - dob.getMonth()

  if (months < 0 || (months === 0 && today.getDate() < dob.getDate())) {
    years--
    months += 12
  }

  if (today.getDate() < dob.getDate()) {
    months--
    if (months < 0) {
      years--
      months += 11
    }
  }

  if (years > 0) {
    return `${years} Yrs${months > 0 ? `, ${months} Mos` : ''}`
  }
  return `${months} Mos`
}

export default function AddNewAnimal() {
  const navigate = useNavigate()
  const [photoBase64, setPhotoBase64] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [loading, setLoading] = useState(false)

  // Get current date in YYYY-MM-DD format for HTML max attribute
  const todayDateString = new Date().toISOString().split('T')[0]

  // Convert uploaded image file to Base64 string
  const handlePhotoChange = (e) => {
    const file = e.target.files[0]
    if (!file) return

    // Limit to 5MB to prevent large payload errors
    if (file.size > 5 * 1024 * 1024) {
      setErrorMessage('Image size exceeds 5MB. Please upload a smaller image.')
      return
    }

    const reader = new FileReader()
    reader.onloadend = () => {
      setPhotoBase64(reader.result)
      setErrorMessage('')
    }
    reader.onerror = () => {
      setErrorMessage('Failed to read file. Please try again.')
    }
    reader.readAsDataURL(file)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage('')

    const formData = new FormData(e.target)
    const identifier = formData.get('identifier')
    const gender = formData.get('gender')
    const dob = formData.get('dob')
    const breed = formData.get('breed')
    const weightVal = formData.get('weight')

    const calvingDateVal = formData.get('calving_date')

    // 1. Required fields validation
    if (!identifier || !gender || !dob || !breed || !weightVal) {
      setErrorMessage('Please fill in all required fields.')
      return
    }

    // 2. Weight validation (must be positive & >= 0.1)
    const weight = parseFloat(weightVal)
    if (isNaN(weight) || weight < 0.1) {
      setErrorMessage('Initial Body Weight must be a positive number greater than or equal to 0.1 KG.')
      return
    }

    // 3. Date of birth validation (no future dates)
    const dobDate = new Date(dob)
    const today = new Date()
    dobDate.setHours(0, 0, 0, 0)
    today.setHours(0, 0, 0, 0)
    if (dobDate > today) {
      setErrorMessage('Date of Birth cannot be in the future.')
      return
    }

    // 4. Calving date validation (optional)
    if (calvingDateVal) {
      const calvingDate = new Date(calvingDateVal)
      calvingDate.setHours(0, 0, 0, 0)
      if (calvingDate > today) {
        setErrorMessage('Last Calving Date cannot be in the future.')
        return
      }
      if (calvingDate < dobDate) {
        setErrorMessage('Last Calving Date cannot be before the Date of Birth.')
        return
      }
    }

    setLoading(true)

    const payload = {
      identifier: identifier.trim(),
      gender,
      dob,
      breed,
      weight,
      profile_photo: photoBase64 || null,
      calving_date: calvingDateVal || null,
      status: 'Healthy',
    }


    const token = localStorage.getItem('token')

    try {
      const response = await fetch('http://127.0.0.1:8000/api/cattle', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(payload),
      })

      const data = await response.json()
      if (response.ok) {
        navigate('/health/herd-registry')
      } else {
        setErrorMessage(data.detail || 'Failed to save animal record. Please verify fields.')
      }
    } catch (err) {
      setErrorMessage('Cannot connect to server. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-8rem)]">
      <div className="max-w-2xl w-full">
        <div className="bg-surface-container-high rounded-xl p-6 md:p-10 relative overflow-hidden border border-outline-variant/10 shadow-2xl">
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/5 blur-[100px] rounded-full"></div>

          <div className="relative">
            <header className="mb-8">
              <h2 className="text-2xl font-black text-white tracking-tight uppercase">Register New Animal</h2>
              <p className="text-sm text-on-surface-variant mt-2 font-medium">
                Add a new subject to the Sentinel intelligence network.
              </p>
            </header>

            {errorMessage && (
              <div className="mb-6 p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider">
                {errorMessage}
              </div>
            )}

            <form className="space-y-6" onSubmit={handleSubmit} noValidate>
              {/* Profile Photo Upload */}
              <div className="space-y-2">
                <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                  Profile Photo Upload
                </label>
                <div className="flex items-center gap-6 p-4 bg-surface-container-lowest rounded-lg border border-outline-variant/20">
                  <div className="w-20 h-20 rounded-full bg-surface-container-highest overflow-hidden border border-primary/20 flex-shrink-0 flex items-center justify-center relative group">
                    {photoBase64 ? (
                      <img
                        alt="Profile preview"
                        className="w-full h-full object-cover"
                        src={photoBase64}
                      />
                    ) : (
                      <span className="material-symbols-outlined text-3xl text-slate-500">
                        photo_camera
                      </span>
                    )}
                  </div>
                  <div className="flex-1 space-y-2">
                    <input
                      accept="image/*"
                      className="hidden"
                      id="photo-upload"
                      onChange={handlePhotoChange}
                      type="file"
                    />
                    <label
                      htmlFor="photo-upload"
                      className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary/10 hover:bg-primary/20 text-primary text-xs font-bold rounded-lg cursor-pointer transition-all border border-primary/25"
                    >
                      <span className="material-symbols-outlined text-base">upload</span>
                      Select Image File
                    </label>
                    <p className="text-[10px] text-slate-500">
                      Supports JPG, PNG or WEBP (Max 5MB). Converted to Base64 locally.
                    </p>
                  </div>
                </div>
              </div>

              {/* Identifier (Tag ID or Name) */}
              <div className="space-y-2">
                <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                  Identifier (Tag ID or Name)
                </label>
                <input
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white placeholder:text-slate-600 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                  name="identifier"
                  placeholder="e.g., #BT-8842 or Sudu"
                  required
                  type="text"
                />
              </div>

              {/* Gender and DOB */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                    Gender
                  </label>
                  <div className="relative">
                    <select
                      className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                      defaultValue=""
                      name="gender"
                      required
                    >
                      <option disabled value="">
                        Select Gender
                      </option>
                      <option value="Female">Female</option>
                      <option value="Male">Male</option>
                    </select>
                    <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                      expand_more
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                    Date of Birth (DOB)
                  </label>
                  <div className="relative">
                    <input
                      className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all [color-scheme:dark]"
                      name="dob"
                      required
                      type="date"
                      max={todayDateString}
                    />
                  </div>
                </div>
              </div>

              {/* Breed and Weight */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                    Breed
                  </label>
                  <div className="relative">
                    <select
                      className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                      defaultValue=""
                      name="breed"
                      required
                    >
                      <option disabled value="">
                        Select Breed
                      </option>
                      {allBreeds.map(breed => {
                        const isAllowed = sriLankanBreeds.includes(breed.value);
                        return (
                          <option key={breed.value} value={breed.value} disabled={!isAllowed}>
                            {breed.label} {!isAllowed ? "(N/A in SL)" : ""}
                          </option>
                        );
                      })}
                    </select>
                    <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                      expand_more
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                    Initial Body Weight (KG)
                  </label>
                  <div className="relative">
                    <input
                      className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white placeholder:text-slate-600 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                      min="0.1"
                      name="weight"
                      placeholder="0.00"
                      required
                      step="0.01"
                      type="number"
                    />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-500 uppercase">
                      KG
                    </span>
                  </div>
                </div>
              </div>

              {/* Last Calving Date (Optional) */}
              <div className="space-y-2">
                <label className="block text-[11px] font-black tracking-[0.1em] text-primary uppercase">
                  Last Calving Date (Optional)
                </label>
                <div className="relative">
                  <input
                    className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3.5 text-white focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all [color-scheme:dark]"
                    name="calving_date"
                    type="date"
                    max={todayDateString}
                  />
                </div>
              </div>

              {/* Buttons */}
              <div className="pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
                <Link
                  className="text-sm font-bold text-slate-400 hover:text-white transition-colors tracking-wide underline underline-offset-8 decoration-slate-800 hover:decoration-white"
                  to="/health/herd-registry"
                >
                  Cancel
                </Link>
                <button
                  className="w-full md:w-auto px-10 py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-lg font-black text-sm uppercase tracking-widest shadow-xl shadow-primary/20 transition-transform active:scale-[0.98] disabled:opacity-50"
                  disabled={loading}
                  type="submit"
                >
                  {loading ? 'Saving Record...' : 'Save Animal Record'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
