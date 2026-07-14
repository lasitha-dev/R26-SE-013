import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function BCSAnalyzer() {
  const [cattleList, setCattleList] = useState([])
  const [selectedCattleId, setSelectedCattleId] = useState('')
  const [confidence, setConfidence] = useState(0.5)
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [photoDate, setPhotoDate] = useState(new Date().toISOString().split('T')[0])

  useEffect(() => {
    const fetchCattle = async () => {
      try {
        const token = localStorage.getItem('token')
        const response = await fetch('http://127.0.0.1:8000/api/cattle', {
          headers: {
            Authorization: token ? `Bearer ${token}` : ''
          }
        })
        if (response.ok) {
          const data = await response.json()
          setCattleList(data || [])
        }
      } catch (err) {
        console.error('Error fetching cattle list:', err)
      }
    }
    fetchCattle()
  }, [])

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      setImageFile(file)
      setImagePreview(URL.createObjectURL(file))
      setResult(null)
      setErrorMessage('')
      setSuccessMessage('')
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setImageFile(file)
      setImagePreview(URL.createObjectURL(file))
      setResult(null)
      setErrorMessage('')
      setSuccessMessage('')
    }
  }

  const handleAnalyze = async (e) => {
    e.preventDefault()
    if (!imageFile) {
      setErrorMessage('Please upload or drag a cow image to analyze.')
      return
    }

    setLoading(true)
    setErrorMessage('')
    setSuccessMessage('')
    setResult(null)

    const formData = new FormData()
    formData.append('file', imageFile)
    formData.append('confidence', confidence)
    if (selectedCattleId) {
      formData.append('cattle_id', selectedCattleId)
      formData.append('photo_date', photoDate)
    }

    try {
      const token = localStorage.getItem('token')
      const response = await fetch('http://127.0.0.1:8000/api/monitor/predict-bcs', {
        method: 'POST',
        headers: {
          Authorization: token ? `Bearer ${token}` : ''
        },
        body: formData
      })

      if (response.ok) {
        const data = await response.json()
        setResult(data)
        if (selectedCattleId) {
          const selectedCattle = cattleList.find(c => c.id === selectedCattleId)
          setSuccessMessage(
            `Success: Body Condition Score for ${selectedCattle?.identifier || 'Selected Cow'} updated to ${data.bcs_score} in database.`
          )
        }
      } else {
        const errorData = await response.json()
        setErrorMessage(errorData.detail || 'Prediction failed. Please try a different image.')
      }
    } catch (err) {
      setErrorMessage('Cannot connect to machine learning server. Ensure backend is active.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header Area */}
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
          Standalone BCS Analyzer
        </h2>
        <p className="text-slate-400">
          Upload 2D cow images to dynamically detect coordinates using YOLOv8, crop the region, and compute Body Condition Scoring via CNN regression.
        </p>
        <div className="h-1 w-24 bg-primary rounded-full mt-1"></div>
      </div>

      {successMessage && (
        <div className="p-4 bg-primary/10 border border-primary/20 text-primary rounded-lg text-xs font-bold uppercase tracking-wider">
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="p-4 bg-error/15 border border-error/30 text-error rounded-lg text-xs font-bold uppercase tracking-wider">
          {errorMessage}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Side - Configuration and Upload Form */}
        <div className="lg:col-span-5 bg-surface-container-low rounded-2xl p-6 border border-white/5 space-y-6">
          <h3 className="text-base font-bold text-white uppercase tracking-tight pb-3 border-b border-white/5">
            Diagnostic Configuration
          </h3>

          <form onSubmit={handleAnalyze} className="space-y-6">
            {/* Subject Selection */}
            <div className="space-y-2">
              <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                Associate with Registered Cattle (Optional)
              </label>
              <div className="relative">
                <select
                  className="w-full appearance-none bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3.5 px-4 text-sm font-medium text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                  value={selectedCattleId}
                  onChange={(e) => setSelectedCattleId(e.target.value)}
                >
                  <option value="">-- Unregistered Cattle (No Database Sync) --</option>
                  {cattleList.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.identifier} [{c.breed}]
                    </option>
                  ))}
                </select>
                <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                  expand_more
                </span>
              </div>
            </div>

            {/* Photo Capture Date - visible/required only if cattle is selected */}
            {selectedCattleId && (
              <div className="space-y-2 animate-fadeIn">
                <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                  Photo Capture Date
                </label>
                <input
                  type="date"
                  className="w-full bg-surface-container-lowest border border-outline-variant/20 rounded-lg py-3 px-4 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary transition-all [color-scheme:dark]"
                  value={photoDate}
                  onChange={(e) => setPhotoDate(e.target.value)}
                  max={new Date().toISOString().split('T')[0]}
                  required
                />
              </div>
            )}

            {/* Confidence Limit Slider */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                  YOLOv8 Detection Confidence Limit
                </label>
                <span className="text-primary font-black text-sm">{confidence.toFixed(2)}</span>
              </div>
              <input
                className="w-full h-1.5 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary"
                min="0.10"
                max="0.95"
                step="0.05"
                value={confidence}
                onChange={(e) => setConfidence(parseFloat(e.target.value))}
                type="range"
              />
              <div className="flex justify-between text-[9px] text-slate-500 font-bold">
                <span>0.10 (HIGH RECALL)</span>
                <span>0.95 (HIGH PRECISION)</span>
              </div>
            </div>

            {/* Drag & Drop Upload Zone */}
            <div className="space-y-2">
              <label className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                Bovine Profile Image
              </label>
              <div
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                className={`relative border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center transition-all ${
                  dragActive ? 'border-primary bg-primary/5' : 'border-white/10 hover:border-white/20'
                }`}
              >
                <input
                  type="file"
                  id="image-file-input"
                  className="hidden"
                  accept="image/*"
                  onChange={handleFileChange}
                />
                
                {imagePreview ? (
                  <div className="space-y-4">
                    <img
                      src={imagePreview}
                      alt="Preview"
                      className="max-h-48 rounded-lg object-cover mx-auto border border-white/10 shadow-lg"
                    />
                    <label
                      htmlFor="image-file-input"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-surface-container-highest hover:bg-surface-bright text-xs font-bold rounded-lg cursor-pointer transition-all border border-white/5"
                    >
                      <span className="material-symbols-outlined text-sm">photo_library</span>
                      Replace Image
                    </label>
                  </div>
                ) : (
                  <label htmlFor="image-file-input" className="cursor-pointer space-y-3 block w-full">
                    <span className="material-symbols-outlined text-4xl text-slate-500 animate-pulse">cloud_upload</span>
                    <div className="text-sm font-bold text-white">Drag and drop or click to upload cow image</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider">Supports JPEG, PNG, WEBP</div>
                  </label>
                )}
              </div>
            </div>

            <button
              className="w-full py-4 bg-primary hover:opacity-90 text-on-primary font-black text-xs uppercase tracking-wider rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-primary/10 disabled:opacity-50"
              type="submit"
              disabled={loading || !imageFile}
            >
              {loading ? (
                <>
                  <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                  Analyzing Bovine Anatomy...
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-sm">troubleshoot</span>
                  Analyze Image
                </>
              )}
            </button>
          </form>
        </div>

        {/* Right Side - Results Display */}
        <div className="lg:col-span-7 bg-surface-container-low rounded-2xl p-6 border border-white/5 flex flex-col min-h-[500px]">
          <h3 className="text-base font-bold text-white uppercase tracking-tight pb-3 border-b border-white/5 mb-6">
            Vision Diagnostic Result
          </h3>

          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center space-y-3">
              <span className="material-symbols-outlined text-5xl text-primary animate-spin">cyclone</span>
              <p className="text-sm font-bold text-white uppercase tracking-widest animate-pulse">
                Extracting cow coordinates...
              </p>
              <p className="text-xs text-slate-500 max-w-xs">
                YOLOv8 is analyzing shapes while Keras CNN regression computes localized Body Condition Scoring.
              </p>
            </div>
          ) : result ? (
            <div className="space-y-6 flex-1 flex flex-col">
              {/* BCS Metric Glow Card */}
              <div className="p-6 bg-gradient-to-r from-primary-container/20 to-primary-container/5 border border-primary/25 rounded-2xl flex items-center justify-between shadow-[0_0_30px_rgba(78,222,163,0.05)]">
                <div>
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Predicted BCS Score</h4>
                  <p className="text-[10px] text-slate-500 font-medium">OPTIMAL SCORE RANGE: 3.0 - 3.5</p>
                </div>
                <div className="text-right">
                  <div className="text-5xl font-black text-primary font-display tracking-tighter">
                    {result.bcs_score.toFixed(2)}
                  </div>
                  <div className="text-[10px] text-slate-400 font-bold uppercase mt-1">
                    Detection Conf: {(result.detection_conf * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Bounding box and Cropped side-by-side */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1">
                {/* Annotated Box */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                    YOLOv8 Detection (Annotated Box)
                  </label>
                  <div className="border border-white/5 rounded-xl overflow-hidden bg-surface-container-lowest/50 h-64 md:h-80 flex items-center justify-center">
                    <img
                      src={result.annotated_image}
                      alt="Annotated"
                      className="w-full h-full object-contain"
                    />
                  </div>
                </div>

                {/* Cropped ROI */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                    CNN Input ROI (Cropped 30px Padding)
                  </label>
                  <div className="border border-white/5 rounded-xl overflow-hidden bg-surface-container-lowest/50 h-64 md:h-80 flex items-center justify-center">
                    <img
                      src={result.crop_image}
                      alt="Cropped ROI"
                      className="w-full h-full object-contain"
                    />
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-450">
              <span className="material-symbols-outlined text-6xl text-slate-600 mb-3">camera_front</span>
              <p className="text-sm font-bold text-slate-400 uppercase tracking-widest">
                Awaiting Diagnostics Image Input
              </p>
              <p className="text-xs text-slate-500 max-w-xs mt-1">
                Drag or select a bovine profile photo and click Analyze Image to view condition scores.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
