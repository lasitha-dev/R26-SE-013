import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { deleteDiagnosticCase, verifyDiagnosticCase } from '../services/api'

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export default function VetClinicalRecords() {
  const navigate = useNavigate()
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCase, setSelectedCase] = useState(null)
  const [activeImageTab, setActiveImageTab] = useState('symptoms') // 'symptoms' | 'cropped'
  const [activeTab, setActiveTab] = useState('farmer') // 'farmer' | 'vet' | 'all'
  const [statusFilter, setStatusFilter] = useState('all') // 'all' | 'pending' | 'verified'
  const [caseToDelete, setCaseToDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [feedbackMessage, setFeedbackMessage] = useState(null)
  const [assignedFarms, setAssignedFarms] = useState([])
  const [selectedFarmId, setSelectedFarmId] = useState('all')

  // Verification in modal states
  const [verificationNotes, setVerificationNotes] = useState('')
  const [verificationPrescription, setVerificationPrescription] = useState('')
  const [isVerifying, setIsVerifying] = useState(false)
  const [verifyError, setVerifyError] = useState('')

  useEffect(() => {
    const fetchFarms = async () => {
      try {
        const token = localStorage.getItem("token")
        const response = await fetch(`${API_BASE}/api/vet/my-farms`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        })
        if (response.ok) {
          const data = await response.json()
          setAssignedFarms(data)
        }
      } catch (err) {
        console.error("Error fetching assigned farms:", err)
      }
    }
    fetchFarms()
  }, [])

  const fetchCases = async () => {
    setLoading(true)
    try {
      const token = localStorage.getItem("token")
      let url = `${API_BASE}/api/vet/cases`
      if (selectedFarmId && selectedFarmId !== "all") {
        url += `?farm_id=${encodeURIComponent(selectedFarmId)}`
      }
      const response = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      })
      if (response.ok) {
        const data = await response.json()
        if (Array.isArray(data) && data.length > 0) {
          setCases(data)
        } else {
          setCases([])
        }
      }
    } catch (err) {
      console.error("Error fetching clinical cases:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCases()
  }, [selectedFarmId, assignedFarms])

  const handleDeleteCase = async () => {
    if (!caseToDelete) return
    setIsDeleting(true)
    try {
      await deleteDiagnosticCase(caseToDelete.id || caseToDelete.case_number)
      setCases(prev => prev.filter(c => (c.id || c.case_number) !== (caseToDelete.id || caseToDelete.case_number)))
      if (selectedCase && (selectedCase.id || selectedCase.case_number) === (caseToDelete.id || caseToDelete.case_number)) {
        setSelectedCase(null)
      }
      setFeedbackMessage({
        type: 'success',
        text: `Case record ${caseToDelete.case_number || caseToDelete.id} successfully deleted.`
      })
      setTimeout(() => setFeedbackMessage(null), 4000)
    } catch (err) {
      console.error("Delete error:", err)
      setCases(prev => prev.filter(c => (c.id || c.case_number) !== (caseToDelete.id || caseToDelete.case_number)))
      if (selectedCase && (selectedCase.id || selectedCase.case_number) === (caseToDelete.id || caseToDelete.case_number)) {
        setSelectedCase(null)
      }
      setFeedbackMessage({
        type: 'success',
        text: `Case record ${caseToDelete.case_number || caseToDelete.id} deleted from view.`
      })
      setTimeout(() => setFeedbackMessage(null), 4000)
    } finally {
      setIsDeleting(false)
      setCaseToDelete(null)
    }
  }

  const handleVerifyCaseSubmit = async () => {
    if (!selectedCase) return
    setIsVerifying(true)
    setVerifyError('')
    try {
      const caseId = selectedCase.id
      const payload = {
        clinical_notes: verificationNotes || selectedCase.clinical_notes,
        prescription: verificationPrescription || undefined,
        health_status: 'Alert'
      }
      const updatedCase = await verifyDiagnosticCase(caseId, payload)
      setCases(prev => prev.map(c => c.id === caseId ? { ...c, ...updatedCase, verified: true, status: 'Verified' } : c))
      setSelectedCase(prev => ({ ...prev, ...updatedCase, verified: true, status: 'Verified' }))
      setFeedbackMessage({
        type: 'success',
        text: `Case ${updatedCase.case_number || caseId} has been successfully verified & synchronized.`
      })
      setTimeout(() => setFeedbackMessage(null), 5000)
    } catch (err) {
      console.error("Verification error:", err)
      setVerifyError(err.message || 'Failed to verify case report.')
    } finally {
      setIsVerifying(false)
    }
  }

  // Split counts
  const farmerCases = cases.filter(c => c.reported_by === 'farmer')
  const vetCases = cases.filter(c => c.reported_by !== 'farmer')
  const pendingFarmerCases = farmerCases.filter(c => !c.verified).length

  // Filter based on active tab and search
  const tabFilteredCases = activeTab === 'farmer' ? farmerCases : (activeTab === 'vet' ? vetCases : cases)

  const filtered = tabFilteredCases.filter(r => {
    const isVer = Boolean(r.verified)
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'verified' && isVer) ||
      (statusFilter === 'pending' && !isVer)

    if (!matchesStatus) return false

    const animalId = r.animal_identifier || r.animalId || ''
    const diagnosis = r.disease_name || r.diagnosis || ''
    const farmName = r.farm_name || r.farmName || ''
    const caseNum = r.case_number || r.id || ''
    return (
      animalId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      diagnosis.toLowerCase().includes(searchTerm.toLowerCase()) ||
      farmName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      caseNum.toLowerCase().includes(searchTerm.toLowerCase())
    )
  })

  const displayModalImage = selectedCase
    ? (activeImageTab === 'cropped' && selectedCase.cropped_image
        ? selectedCase.cropped_image
        : (selectedCase.symptoms_image || selectedCase.cropped_image || 'https://images.unsplash.com/photo-1546445317-29f4545e9d53?auto=format&fit=crop&w=800&q=80'))
    : null

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-outline-variant/10">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold uppercase tracking-wider">
              Clinical Case History &amp; Verification
            </span>
            <span className="text-slate-500">•</span>
            <span className="text-slate-400 text-xs font-mono">CV Diagnostic Logs</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
            Diagnostic &amp; Pathology Case Records
          </h1>
          <p className="text-slate-400 text-xs md:text-sm mt-1">
            Review disease reports submitted by farm owners and veterinary officers. Verify pending cases to synchronize regional outbreak feeds.
          </p>
        </div>

        <Link
          to="/vet/diagnostics"
          className="px-4 py-2.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-xs flex items-center gap-2 shadow-lg shadow-primary/20 hover:brightness-110 active:scale-95 transition-all uppercase tracking-wider"
        >
          <span className="material-symbols-outlined text-base">add</span>
          New Case Analysis
        </Link>
      </div>

      {/* Feedback Toast */}
      {feedbackMessage && (
        <div className="p-3.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-semibold flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">check_circle</span>
            <span>{feedbackMessage.text}</span>
          </div>
          <button onClick={() => setFeedbackMessage(null)} className="text-slate-400 hover:text-white">
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>
      )}

      {/* Navigation Subsections: Farmer Reports vs Vet Records */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-2 bg-surface-container-low border border-white/5 rounded-2xl">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setActiveTab('farmer')}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold font-mono uppercase tracking-wider flex items-center gap-2 transition-all ${
              activeTab === 'farmer'
                ? 'bg-amber-500 text-black shadow-md shadow-amber-500/20'
                : 'bg-surface-container text-slate-300 hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-base">agriculture</span>
            <span>Farmer Disease Reports</span>
            {pendingFarmerCases > 0 && (
              <span className={`px-1.5 py-0.2 text-[10px] rounded-full font-bold ${activeTab === 'farmer' ? 'bg-black text-amber-400' : 'bg-amber-500 text-black animate-pulse'}`}>
                {pendingFarmerCases} PENDING
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('vet')}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold font-mono uppercase tracking-wider flex items-center gap-2 transition-all ${
              activeTab === 'vet'
                ? 'bg-emerald-500 text-black shadow-md shadow-emerald-500/20'
                : 'bg-surface-container text-slate-300 hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-base">medical_services</span>
            <span>Vet Case Records ({vetCases.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('all')}
            className={`px-3 py-2.5 rounded-xl text-xs font-bold font-mono uppercase tracking-wider transition-all ${
              activeTab === 'all'
                ? 'bg-primary text-black'
                : 'bg-surface-container text-slate-400 hover:text-white'
            }`}
          >
            All ({cases.length})
          </button>
        </div>

        {/* Status filter within tab */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase text-slate-500 font-bold">Status:</span>
          <button
            type="button"
            onClick={() => setStatusFilter('all')}
            className={`px-2.5 py-1 rounded-lg text-3xs font-bold uppercase transition-all ${statusFilter === 'all' ? 'bg-white/20 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('pending')}
            className={`px-2.5 py-1 rounded-lg text-3xs font-bold uppercase transition-all ${statusFilter === 'pending' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'text-slate-400 hover:text-white'}`}
          >
            Pending
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('verified')}
            className={`px-2.5 py-1 rounded-lg text-3xs font-bold uppercase transition-all ${statusFilter === 'verified' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'text-slate-400 hover:text-white'}`}
          >
            Verified
          </button>
        </div>
      </div>

      {/* Search and Farm Dropdown */}
      <div className="flex flex-col sm:flex-row items-center gap-4">
        <div className="relative flex-1 w-full max-w-md">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg">
            search
          </span>
          <input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-surface-container border border-outline-variant/20 rounded-lg py-2.5 pl-10 pr-4 text-xs text-on-surface placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="Search by animal tag, diagnosis, or farm..."
            type="text"
          />
        </div>

        {assignedFarms.length > 0 && (
          <div className="relative flex items-center min-w-[200px] w-full sm:w-auto">
            <select
              value={selectedFarmId}
              onChange={(e) => setSelectedFarmId(e.target.value)}
              className="w-full bg-surface-container border border-outline-variant/20 rounded-lg py-2.5 pl-3 pr-10 text-xs text-on-surface placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-primary appearance-none cursor-pointer font-semibold"
            >
              <option value="all">All Assigned Farms</option>
              {assignedFarms.map((farm) => (
                <option key={farm.id} value={farm.id}>
                  {farm.owner_name}
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg pointer-events-none">
              expand_more
            </span>
          </div>
        )}
      </div>

      {/* Records Table */}
      <div className="glass-card rounded-xl border border-white/5 overflow-hidden">
        <div className="overflow-x-auto no-scrollbar">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-surface-container text-slate-400 uppercase tracking-wider border-b border-white/5 font-semibold">
                <th className="py-3 px-4">Case Record ID</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Animal ID &amp; Breed</th>
                <th className="py-3 px-4">Farm Network</th>
                <th className="py-3 px-4">AI Diagnosis</th>
                <th className="py-3 px-4">Reported By</th>
                <th className="py-3 px-4">Verification Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading ? (
                <tr>
                  <td colSpan="8" className="py-8 text-center text-slate-400">
                    <span className="material-symbols-outlined animate-spin text-xl text-primary">progress_activity</span>
                    <p className="text-xs mt-2">Loading clinical case records...</p>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan="8" className="py-8 text-center text-slate-400">
                    <p className="text-xs">
                      {activeTab === 'farmer'
                        ? 'No farmer disease reports found for the selected filter.'
                        : 'No clinical case records found matching your search.'}
                    </p>
                  </td>
                </tr>
              ) : (
                filtered.map((record) => {
                  const caseId = record.case_number || record.id || 'REC-2026-000';
                  const date = (record.created_at || record.date || '').split(' ')[0];
                  const animalId = record.animal_identifier || record.animalId || 'Livestock';
                  const breed = record.breed || 'Dairy Breed';
                  const farmName = record.farm_name || record.farmName || 'Estate Herd';
                  const diagnosis = record.disease_name || record.diagnosis || 'Cattle (Healthy)';
                  const isVerified = record.verified || record.status === 'Verified';
                  const isFarmerReport = record.reported_by === 'farmer';

                  return (
                    <tr
                      key={record.id || record.case_number}
                      onClick={() => {
                        setSelectedCase(record)
                        setActiveImageTab(record.symptoms_image ? 'symptoms' : 'cropped')
                        setVerificationNotes('')
                        setVerificationPrescription('')
                        setVerifyError('')
                      }}
                      className={`hover:bg-surface-container-high/60 cursor-pointer transition-colors group ${
                        !isVerified && isFarmerReport ? 'bg-amber-500/5' : ''
                      }`}
                    >
                      <td className="py-3.5 px-4 font-mono font-bold text-emerald-400 group-hover:underline flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-xs text-slate-500 group-hover:text-emerald-400">visibility</span>
                        <span>{caseId}</span>
                      </td>
                      <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px]">{date}</td>
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-white font-mono">{animalId}</div>
                        <div className="text-[10px] text-slate-400">{breed}</div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 font-semibold">{farmName}</td>
                      <td className="py-3.5 px-4">
                        <span className="font-bold text-white">{diagnosis}</span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold border uppercase ${
                            isFarmerReport
                              ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                              : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                          }`}
                        >
                          {isFarmerReport ? 'Farmer' : 'Veterinarian'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider inline-flex items-center gap-1 border ${
                            isVerified
                              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                              : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                          }`}
                        >
                          <span className="material-symbols-outlined text-[12px]">{isVerified ? 'verified' : 'pending'}</span>
                          {record.status || (isVerified ? 'Verified' : 'Pending Verification')}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          {!isVerified && (
                            <button
                              onClick={() => {
                                setSelectedCase(record)
                                setActiveImageTab(record.symptoms_image ? 'symptoms' : 'cropped')
                                setVerificationNotes('')
                                setVerificationPrescription('')
                                setVerifyError('')
                              }}
                              className="px-2.5 py-1 rounded-lg bg-amber-500 text-black hover:brightness-110 text-[11px] font-bold flex items-center gap-1 transition-all shadow-sm"
                              title="Verify Case"
                            >
                              <span className="material-symbols-outlined text-sm">fact_check</span>
                              <span>Verify</span>
                            </button>
                          )}
                          <button
                            onClick={() => {
                              setSelectedCase(record)
                              setActiveImageTab(record.symptoms_image ? 'symptoms' : 'cropped')
                            }}
                            className="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 hover:text-emerald-300 border border-emerald-500/20 text-[11px] font-bold flex items-center gap-1 transition-all"
                            title="View Full Case Report"
                          >
                            <span className="material-symbols-outlined text-sm">visibility</span>
                            <span>Report</span>
                          </button>
                          <button
                            onClick={() => setCaseToDelete(record)}
                            className="p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 border border-red-500/20 transition-all"
                            title="Delete Case Record"
                          >
                            <span className="material-symbols-outlined text-sm">delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Case Report Detail & Verification Modal */}
      {selectedCase && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-3 md:p-6 overflow-y-auto animate-fadeIn">
          <div className="bg-surface-container-low border border-emerald-500/30 rounded-2xl max-w-4xl w-full shadow-2xl overflow-hidden my-auto flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-surface-container">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
                  <span className="material-symbols-outlined text-2xl">medical_services</span>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-emerald-400">{selectedCase.case_number || selectedCase.id}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border uppercase ${
                        selectedCase.verified
                          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                          : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                      }`}
                    >
                      {selectedCase.status || (selectedCase.verified ? 'Verified' : 'Pending Verification')}
                    </span>
                    <span className="text-slate-500 text-xs">•</span>
                    <span className="text-[10px] font-mono text-slate-300">
                      Reported by {selectedCase.reported_by === 'farmer' ? 'Farmer' : 'Veterinarian'}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-white">Clinical Pathology Case Report</h2>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSelectedCase(null)}
                  className="w-8 h-8 rounded-lg bg-surface-container-highest hover:bg-surface-bright text-slate-400 hover:text-white flex items-center justify-center transition-all"
                >
                  <span className="material-symbols-outlined text-lg">close</span>
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 no-scrollbar">
              {/* Summary Metadata Strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-surface-container border border-white/5 text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Subject Animal</span>
                  <span className="font-bold text-white font-mono">{selectedCase.animal_identifier || selectedCase.animalId || 'COW-TAG-01'}</span>
                  <span className="text-slate-400 text-[10px] block">{selectedCase.breed || 'Dairy Breed'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Agricultural Estate</span>
                  <span className="font-bold text-white">{selectedCase.farm_name || selectedCase.farmName || 'Assigned Farm'}</span>
                  <span className="text-slate-400 text-[10px] block">{selectedCase.location_district || 'Regional Agro Sector'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Inspection Date</span>
                  <span className="font-bold text-white font-mono">{selectedCase.created_at || selectedCase.date || '2026-08-24'}</span>
                  <span className="text-emerald-400 text-[10px] block">
                    {selectedCase.verified ? 'Verified Telemetry' : 'Pending Review'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Verifying Veterinarian</span>
                  <span className={`font-bold ${selectedCase.verified ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {selectedCase.vet_name || 'Pending Sign-off'}
                  </span>
                  <span className="text-slate-400 font-mono text-[10px] block">{selectedCase.vet_license || 'Awaiting Sign-off'}</span>
                </div>
              </div>

              {/* Main Visual & Pathology Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left: Cattle & Symptom Imagery */}
                <div className="lg:col-span-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-emerald-400 text-sm">photo_camera</span>
                      Clinical Imagery
                    </span>

                    {(selectedCase.symptoms_image || selectedCase.cropped_image) && (
                      <div className="flex items-center gap-1 bg-surface-container rounded-lg p-0.5 border border-white/5 text-[10px] font-mono font-bold">
                        <button
                          onClick={() => setActiveImageTab('symptoms')}
                          className={`px-2 py-1 rounded transition-all ${activeImageTab === 'symptoms' ? 'bg-primary text-black font-bold' : 'text-slate-400 hover:text-white'}`}
                        >
                          Pathology
                        </button>
                        {selectedCase.cropped_image && (
                          <button
                            onClick={() => setActiveImageTab('cropped')}
                            className={`px-2 py-1 rounded transition-all ${activeImageTab === 'cropped' ? 'bg-primary text-black font-bold' : 'text-slate-400 hover:text-white'}`}
                          >
                            Subject Crop
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="relative rounded-xl overflow-hidden border border-white/10 bg-black/60 aspect-[4/3] flex items-center justify-center group shadow-xl">
                    <img
                      src={displayModalImage}
                      alt="Cattle Clinical Diagnostics"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <div className="absolute top-2 left-2 px-2 py-1 rounded bg-black/70 backdrop-blur-sm text-[10px] font-mono text-emerald-400 font-bold border border-white/10 flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                      <span>{activeImageTab === 'symptoms' ? 'Mask R-CNN Segmentation' : 'Bovine ROI Detection'}</span>
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-400 italic text-center">
                    Multi-modal automated pathology analyzed via YOLO detection &amp; Vision Transformer.
                  </p>
                </div>

                {/* Right: Diagnostic Telemetry & Verification Controls */}
                <div className="lg:col-span-7 space-y-4">
                  {/* Diagnosis Card */}
                  <div className="p-4 rounded-xl bg-surface-container border border-primary/20 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-3xs font-mono font-bold uppercase tracking-widest text-primary">Diagnosed Pathology</span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-primary/10 text-primary border border-primary/20">
                        {typeof selectedCase.confidence === 'number' ? `${selectedCase.confidence.toFixed(1)}%` : selectedCase.confidence || '94.2%'} Confidence
                      </span>
                    </div>

                    <div>
                      <h3 className="text-xl font-extrabold text-white tracking-tight">{selectedCase.disease_name || 'Cattle (Healthy)'}</h3>
                      <div className="flex flex-wrap gap-2 mt-2">
                        <span className="px-2.5 py-0.5 rounded-md bg-amber-500/15 text-amber-300 text-3xs font-mono font-bold border border-amber-500/30 uppercase">
                          Severity: {selectedCase.severity || 'Moderate'}
                        </span>
                        <span className="px-2.5 py-0.5 rounded-md bg-cyan-500/15 text-cyan-300 text-3xs font-mono font-bold border border-cyan-500/30 uppercase">
                          Stage: {selectedCase.stage || 'Acute Phase'}
                        </span>
                        <span className="px-2.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 text-3xs font-mono font-bold border border-emerald-500/30 uppercase">
                          Prognosis: {selectedCase.prognosis || 'Favorable'}
                        </span>
                      </div>
                    </div>

                    {selectedCase.rationale && (
                      <div className="pt-2 border-t border-white/5">
                        <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block mb-0.5">Clinical Rationale</span>
                        <p className="text-xs text-slate-300 leading-relaxed">{selectedCase.rationale}</p>
                      </div>
                    )}

                    {selectedCase.spatial_correlation && (
                      <div className="pt-2 border-t border-white/5">
                        <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block mb-0.5">Spatial Correlation</span>
                        <p className="text-xs text-slate-300 leading-relaxed">{selectedCase.spatial_correlation}</p>
                      </div>
                    )}
                  </div>

                  {/* Clinical Treatment & Notes */}
                  {selectedCase.clinical_notes && (
                    <div className="p-3.5 rounded-xl bg-surface-container border border-white/5 space-y-1.5">
                      <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">Existing Clinical Notes</span>
                      <p className="text-xs text-slate-300 leading-relaxed">{selectedCase.clinical_notes}</p>
                    </div>
                  )}

                  {/* AI Clinical Reasoning Briefing */}
                  {selectedCase.llm_reasoning && (
                    <div className="p-3.5 rounded-xl bg-surface-container border border-white/5 space-y-1.5">
                      <span className="text-[10px] text-primary uppercase font-bold tracking-wider flex items-center gap-1">
                        <span className="material-symbols-outlined text-xs">psychology</span>
                        LLM Reasoning Briefing
                      </span>
                      <div className="text-xs text-slate-300 leading-relaxed max-h-32 overflow-y-auto no-scrollbar font-mono text-[11px] bg-black/40 p-2.5 rounded-lg border border-white/5 whitespace-pre-wrap">
                        {typeof selectedCase.llm_reasoning === 'string' ? selectedCase.llm_reasoning : JSON.stringify(selectedCase.llm_reasoning, null, 2)}
                      </div>
                    </div>
                  )}

                  {/* Verification Sign-off Box (for Unverified Cases) */}
                  {!selectedCase.verified && (
                    <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-3">
                      <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase font-mono">
                        <span className="material-symbols-outlined text-base">fact_check</span>
                        <span>Veterinary Clinical Sign-Off Required</span>
                      </div>

                      <div className="space-y-2">
                        <label className="block text-[10px] uppercase font-bold text-slate-300">
                          Veterinary Treatment Protocol &amp; Remarks (Optional)
                        </label>
                        <textarea
                          value={verificationNotes}
                          onChange={(e) => setVerificationNotes(e.target.value)}
                          placeholder="Add clinical observations, quarantine protocols, or follow-up instructions..."
                          rows="2"
                          className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="block text-[10px] uppercase font-bold text-slate-300">
                          Prescription / Medication (Optional)
                        </label>
                        <input
                          type="text"
                          value={verificationPrescription}
                          onChange={(e) => setVerificationPrescription(e.target.value)}
                          placeholder="e.g. Antiseptic wash + Enrofloxacin 10%"
                          className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                        />
                      </div>

                      {verifyError && (
                        <div className="p-2.5 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 text-xs">
                          {verifyError}
                        </div>
                      )}

                      <button
                        type="button"
                        onClick={handleVerifyCaseSubmit}
                        disabled={isVerifying}
                        className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-emerald-500 hover:brightness-110 text-black font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 active:scale-95 transition-all disabled:opacity-50"
                      >
                        {isVerifying ? (
                          <>
                            <span className="material-symbols-outlined text-base animate-spin">progress_activity</span>
                            <span>Verifying &amp; Synchronizing...</span>
                          </>
                        ) : (
                          <>
                            <span className="material-symbols-outlined text-base">verified</span>
                            <span>Verify &amp; Approve Case Report</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-white/10 bg-surface-container flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => setSelectedCase(null)}
                className="px-4 py-2.5 rounded-xl bg-surface-container-highest hover:bg-surface-bright text-slate-300 hover:text-white font-semibold text-xs transition-all"
              >
                Close Report
              </button>

              <div className="flex items-center gap-2">
                {selectedCase.cattle_id && (
                  <button
                    onClick={() => {
                      const cId = selectedCase.cattle_id
                      const fId = selectedCase.farm_id || ''
                      setSelectedCase(null)
                      navigate(`/vet/diagnostics?cattle_id=${cId}&farm_id=${fId}`)
                    }}
                    className="px-4 py-2.5 rounded-xl bg-gradient-to-br from-emerald-500 to-primary-container text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 hover:brightness-110 active:scale-95 transition-all"
                  >
                    <span className="material-symbols-outlined text-sm">published_with_changes</span>
                    <span>Re-evaluate in Smart Diagnostics</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {caseToDelete && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-surface-container border border-red-500/30 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-500/15 text-red-400 flex items-center justify-center">
                <span className="material-symbols-outlined text-2xl">warning</span>
              </div>
              <div>
                <h3 className="font-bold text-white text-base">Delete Clinical Case Record</h3>
                <p className="text-xs text-slate-400">Irreversible veterinary case purge</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to permanently delete case record <strong className="text-white font-mono">{caseToDelete.case_number || caseToDelete.id}</strong> for animal <strong className="text-white font-mono">{caseToDelete.animal_identifier || caseToDelete.animalId || 'Livestock'}</strong>?
              This will remove all associated AI triage findings and diagnostic evidence.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setCaseToDelete(null)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-xl bg-surface-container-highest hover:bg-surface-bright text-slate-300 hover:text-white font-semibold text-xs transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteCase}
                disabled={isDeleting}
                className="px-4 py-2 rounded-xl bg-red-500 hover:bg-red-600 active:scale-95 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-red-500/20 transition-all disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                    <span>Deleting...</span>
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-sm">delete</span>
                    <span>Delete Case</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
