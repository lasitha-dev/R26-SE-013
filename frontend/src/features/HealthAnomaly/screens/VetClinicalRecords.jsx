import React, { useState } from 'react'
import { Link } from 'react-router-dom'

export default function VetClinicalRecords() {
  const sampleRecords = [
    {
      id: 'REC-2026-081',
      date: '2026-08-23',
      animalId: 'SL-COW-4402',
      breed: 'Holstein-Friesian',
      farmName: 'Highland Dairy Holdings',
      diagnosis: 'Bovine Respiratory Syncytial Virus (BRSV)',
      confidence: '94.2%',
      severity: 'High',
      status: 'Prescription Issued'
    },
    {
      id: 'REC-2026-079',
      date: '2026-08-22',
      animalId: 'SL-COW-1092',
      breed: 'Jersey Cross',
      farmName: 'Greenfield Pastures',
      diagnosis: 'Digital Dermatitis (Foot Rot)',
      confidence: '89.7%',
      severity: 'Moderate',
      status: 'Topical Protocol'
    },
    {
      id: 'REC-2026-072',
      date: '2026-08-20',
      animalId: 'SL-COW-8842',
      breed: 'Ayrshire',
      farmName: 'Highland Dairy Holdings',
      diagnosis: 'Healthy / Minor BCS Variation',
      confidence: '97.5%',
      severity: 'Low',
      status: 'Monitoring'
    },
    {
      id: 'REC-2026-068',
      date: '2026-08-18',
      animalId: 'SL-COW-3110',
      breed: 'Sahiwal',
      farmName: 'Lanka Agro Farmstead',
      diagnosis: 'Bovine Papillomatosis',
      confidence: '91.3%',
      severity: 'Moderate',
      status: 'Review Scheduled'
    }
  ]

  const [searchTerm, setSearchTerm] = useState('')
  const filtered = sampleRecords.filter(
    r =>
      r.animalId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.diagnosis.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.farmName.toLowerCase().includes(searchTerm.toLowerCase())
  )

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
            Historical automated diagnoses, Mask R-CNN segmentation overlays, and clinical treatment notes.
          </p>
        </div>

        <Link
          to="/diagnostics"
          className="px-4 py-2.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-xs flex items-center gap-2 shadow-lg shadow-primary/20 hover:brightness-110 active:scale-95 transition-all uppercase tracking-wider"
        >
          <span className="material-symbols-outlined text-base">add</span>
          New Case Analysis
        </Link>
      </div>

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
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filtered.map((record) => (
                <tr key={record.id} className="hover:bg-surface-container-high/40 transition-colors">
                  <td className="py-3.5 px-4 font-mono font-bold text-emerald-400">{record.id}</td>
                  <td className="py-3.5 px-4 text-slate-400 font-mono">{record.date}</td>
                  <td className="py-3.5 px-4">
                    <div className="font-bold text-white">{record.animalId}</div>
                    <div className="text-[10px] text-slate-500">{record.breed}</div>
                  </td>
                  <td className="py-3.5 px-4 text-slate-300">{record.farmName}</td>
                  <td className="py-3.5 px-4">
                    <span className="font-semibold text-white">{record.diagnosis}</span>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-primary/10 text-primary border border-primary/20">
                      {record.confidence}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-slate-300 font-medium">
                    {record.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
