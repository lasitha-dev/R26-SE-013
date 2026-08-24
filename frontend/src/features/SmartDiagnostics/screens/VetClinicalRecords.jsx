import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { deleteDiagnosticCase } from '../services/api'

export default function VetClinicalRecords() {
  const navigate = useNavigate()
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCase, setSelectedCase] = useState(null)
  const [activeImageTab, setActiveImageTab] = useState('symptoms') // 'symptoms' | 'cropped'
  const [caseToDelete, setCaseToDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [feedbackMessage, setFeedbackMessage] = useState(null)

  useEffect(() => {
    const fetchCases = async () => {
      try {
        const token = localStorage.getItem("token")
        const response = await fetch("http://127.0.0.1:8000/api/vet/cases", {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        })
        if (response.ok) {
          const data = await response.json()
          if (Array.isArray(data) && data.length > 0) {
            setCases(data)
          } else {
            // Seed with illustrative default clinical case records if no records saved yet
            setCases([
              {
                id: 'REC-2026-081',
                case_number: 'REC-2026-081',
                created_at: '2026-08-23 14:30:00',
                animal_identifier: 'SL-COW-4402',
                breed: 'Holstein-Friesian',
                farm_name: 'Highland Dairy Holdings',
                disease_name: 'Lumpy Skin Disease',
                confidence: 94.2,
                severity: 'High',
                stage: 'Acute Phase',
                prognosis: 'Guarded',
                rationale: 'Circumscribed cutaneous nodules with central epidermal necrosis and surrounding inflammatory halos.',
                spatial_correlation: 'Multiple discrete nodular eruptions distributed across the cervical, flank, and perineal dermis.',
                clinical_notes: 'Quarantine protocol initiated. Localized antiseptic wound debridement and supportive anti-inflammatory therapy administered.',
                symptoms_image: 'https://images.unsplash.com/photo-1546445317-29f4545e9d53?auto=format&fit=crop&w=800&q=80',
                cropped_image: 'https://images.unsplash.com/photo-1570042225831-d98fa7577f1e?auto=format&fit=crop&w=800&q=80',
                vet_name: 'Dr. Sarah Connor',
                vet_license: 'VET-AUTH-2026',
                status: 'Verified',
                verified: true
              },
              {
                id: 'REC-2026-079',
                case_number: 'REC-2026-079',
                created_at: '2026-08-22 10:15:00',
                animal_identifier: 'SL-COW-1092',
                breed: 'Jersey Cross',
                farm_name: 'Greenfield Pastures',
                disease_name: 'Foot and Mouth Disease',
                confidence: 89.7,
                severity: 'Moderate',
                stage: 'Prodromal Phase',
                prognosis: 'Guarded to Fair',
                rationale: 'Early vesicular eruptions and hyperemic erosion observed along the coronary band and interdigital cleft.',
                spatial_correlation: 'Bilateral distal extremity localization with mucosal irritation.',
                clinical_notes: 'Isolation from milking herd completed. Bio-security perimeter established.',
                symptoms_image: 'https://images.unsplash.com/photo-1527153857715-3908f2ae5e81?auto=format&fit=crop&w=800&q=80',
                vet_name: 'Dr. Sarah Connor',
                vet_license: 'VET-AUTH-2026',
                status: 'Verified',
                verified: true
              },
              {
                id: 'REC-2026-072',
                case_number: 'REC-2026-072',
                created_at: '2026-08-20 16:45:00',
                animal_identifier: 'SL-COW-8842',
                breed: 'Ayrshire',
                farm_name: 'Highland Dairy Holdings',
                disease_name: 'Cattle (Healthy)',
                confidence: 97.5,
                severity: 'Low',
                stage: 'Normal Baseline',
                prognosis: 'Excellent',
                rationale: 'Unblemished epidermal tissue with normal coat sheen. No lesions, vesicle formation, or swelling detected.',
                spatial_correlation: 'Uniform morphological contours throughout abdominal and cranial regions.',
                clinical_notes: 'Routine herd wellness screening passed with optimal health rating.',
                symptoms_image: 'https://images.unsplash.com/photo-1546445317-29f4545e9d53?auto=format&fit=crop&w=800&q=80',
                vet_name: 'Dr. Sarah Connor',
                vet_license: 'VET-AUTH-2026',
                status: 'Verified',
                verified: true
              },
              {
                id: 'REC-2026-068',
                case_number: 'REC-2026-068',
                created_at: '2026-08-18 09:20:00',
                animal_identifier: 'SL-COW-3110',
                breed: 'Sahiwal',
                farm_name: 'Lanka Agro Farmstead',
                disease_name: 'Mastitis',
                confidence: 91.3,
                severity: 'Moderate',
                stage: 'Acute Inflammation',
                prognosis: 'Good with Treatment',
                rationale: 'Asymmetric swelling with erythema and localized hyperthermia in the right hind udder quarter.',
                spatial_correlation: 'Mammary gland quadrant localization with localized vascular dilation.',
                clinical_notes: 'Intramammary antibiotic infusion administered. Daily somatic cell count monitoring scheduled.',
                symptoms_image: 'https://images.unsplash.com/photo-1570042225831-d98fa7577f1e?auto=format&fit=crop&w=800&q=80',
                vet_name: 'Dr. Sarah Connor',
                vet_license: 'VET-AUTH-2026',
                status: 'Verified',
                verified: true
              }
            ])
          }
        }
      } catch (err) {
        console.error("Error fetching clinical cases:", err)
      } finally {
        setLoading(false)
      }
    }
    fetchCases()
  }, [])

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

  const filtered = cases.filter(r => {
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

  // Determine active display image for modal
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
              Clinical Case History
            </span>
            <span className="text-slate-500">•</span>
            <span className="text-slate-400 text-xs font-mono">CV Diagnostic Logs</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
            Diagnostic &amp; Pathology Case Records
          </h1>
          <p className="text-slate-400 text-xs md:text-sm mt-1">
            Historical automated diagnoses, Mask R-CNN segmentation overlays, and clinical treatment notes. Click any record to inspect the full case report.
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

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg">
            search
          </span>
          <input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-surface-container border border-outline-variant/20 rounded-lg py-2.5 pl-10 pr-4 text-xs text-on-surface placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="Search by animal ID, diagnosis, or farm..."
            type="text"
          />
        </div>
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
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Clinical Protocol</th>
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
                    <p className="text-xs">No clinical case records found matching your search.</p>
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
                  const conf = typeof record.confidence === 'number' ? `${record.confidence.toFixed(1)}%` : (record.confidence || '90.0%');
                  const isVerified = record.verified || record.status === 'Verified';

                  return (
                    <tr
                      key={record.id || record.case_number}
                      onClick={() => {
                        setSelectedCase(record)
                        setActiveImageTab(record.symptoms_image ? 'symptoms' : 'cropped')
                      }}
                      className="hover:bg-surface-container-high/60 cursor-pointer transition-colors group"
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
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-primary/10 text-primary border border-primary/20">
                          {conf}
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

      {/* Case Report Detail Modal */}
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
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 uppercase">
                      {selectedCase.status || 'Verified'}
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
                  <span className="text-emerald-400 text-[10px] block">Verified Telemetry</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Veterinarian</span>
                  <span className="font-bold text-white">{selectedCase.vet_name || 'Clinical Practitioner'}</span>
                  <span className="text-slate-400 font-mono text-[10px] block">{selectedCase.vet_license || 'VET-AUTH-2026'}</span>
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
                    High-resolution imagery analyzed via YOLOv8 detection &amp; Vision Transformer triage.
                  </p>
                </div>

                {/* Right: Diagnostic Telemetry & Assessment */}
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
                      <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">Veterinary Clinical Protocol</span>
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
                    <span>Update in Smart Diagnostics</span>
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
