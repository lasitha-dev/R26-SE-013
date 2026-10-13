import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export default function FarmerCaseHistory() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL'); // 'ALL' | 'PENDING' | 'VERIFIED'
  const [selectedCase, setSelectedCase] = useState(null);
  const [activeImageTab, setActiveImageTab] = useState('symptoms');
  const navigate = useNavigate();

  useEffect(() => {
    fetchFarmerCases();
  }, []);

  const fetchFarmerCases = async () => {
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/api/vet/cases`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (response.ok) {
        const data = await response.json();
        setCases(Array.isArray(data) ? data : []);
      } else {
        const err = await response.json();
        setError(err.detail || 'Failed to load case history.');
      }
    } catch (err) {
      setError('Unable to connect to server. Ensure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const filteredCases = cases.filter((item) => {
    const isVerified = Boolean(item.verified);
    const matchesStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'VERIFIED' && isVerified) ||
      (statusFilter === 'PENDING' && !isVerified);

    const q = searchQuery.toLowerCase().trim();
    if (!q) return matchesStatus;

    const animalId = (item.animal_identifier || '').toLowerCase();
    const disease = (item.disease_name || '').toLowerCase();
    const caseNum = (item.case_number || '').toLowerCase();
    const breed = (item.breed || '').toLowerCase();

    return matchesStatus && (animalId.includes(q) || disease.includes(q) || caseNum.includes(q) || breed.includes(q));
  });

  const totalReports = cases.length;
  const pendingReports = cases.filter((c) => !c.verified).length;
  const verifiedReports = cases.filter((c) => c.verified).length;
  const alertReports = cases.filter((c) => {
    const d = (c.disease_name || '').toLowerCase();
    return d !== 'cattle' && d !== 'cattle (healthy)' && d !== 'healthy' && d !== 'undetermined';
  }).length;

  const displayModalImage =
    activeImageTab === 'cropped'
      ? selectedCase?.cropped_image || selectedCase?.symptoms_image || 'https://placehold.co/600x400/131b2e/38bdf8?text=ROI+Subject+Crop'
      : selectedCase?.symptoms_image || selectedCase?.cropped_image || 'https://placehold.co/600x400/131b2e/10b981?text=Clinical+Imagery';

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-4 border-b border-outline-variant/10">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2.5 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-3xs font-mono font-bold uppercase tracking-wider">
              Diagnostic History &amp; Records
            </span>
            <span className="text-outline text-3xs">•</span>
            <span className="text-emerald-400 text-3xs font-mono">Synced with Clinical Lead</span>
          </div>
          <h1 className="text-2xl md:text-3xl lg:text-4xl font-extrabold text-on-surface tracking-tight">
            Livestock Diagnostic Case History
          </h1>
          <p className="text-on-surface-variant text-xs md:text-sm max-w-2xl mt-1.5 leading-relaxed">
            Review all AI diagnostic reports submitted for your herd and track clinical verification by your assigned veterinarian.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/health/diagnostics"
            className="px-4 py-2.5 rounded-xl primary-gradient text-on-primary font-bold text-xs flex items-center gap-2 shadow-lg shadow-primary/15 hover:brightness-105 active:scale-95 transition-all uppercase tracking-wider"
          >
            <span className="material-symbols-outlined text-base">psychology</span>
            <span>Run New AI Scan</span>
          </Link>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-surface-container-low border border-white/5 shadow-card-subtle flex flex-col justify-between">
          <div className="flex items-center justify-between text-outline text-xs font-bold uppercase">
            <span>Total Reports</span>
            <span className="material-symbols-outlined text-primary text-lg">folder</span>
          </div>
          <p className="text-2xl font-black text-white font-mono mt-2">{totalReports}</p>
        </div>

        <div className="p-4 rounded-xl bg-surface-container-low border border-amber-500/20 shadow-card-subtle flex flex-col justify-between">
          <div className="flex items-center justify-between text-amber-400 text-xs font-bold uppercase">
            <span>Pending Review</span>
            <span className="material-symbols-outlined text-amber-400 text-lg">pending</span>
          </div>
          <p className="text-2xl font-black text-amber-400 font-mono mt-2">{pendingReports}</p>
        </div>

        <div className="p-4 rounded-xl bg-surface-container-low border border-emerald-500/20 shadow-card-subtle flex flex-col justify-between">
          <div className="flex items-center justify-between text-emerald-400 text-xs font-bold uppercase">
            <span>Vet Verified</span>
            <span className="material-symbols-outlined text-emerald-400 text-lg">verified</span>
          </div>
          <p className="text-2xl font-black text-emerald-400 font-mono mt-2">{verifiedReports}</p>
        </div>

        <div className="p-4 rounded-xl bg-surface-container-low border border-rose-500/20 shadow-card-subtle flex flex-col justify-between">
          <div className="flex items-center justify-between text-rose-400 text-xs font-bold uppercase">
            <span>Pathology Alerts</span>
            <span className="material-symbols-outlined text-rose-400 text-lg">warning</span>
          </div>
          <p className="text-2xl font-black text-rose-400 font-mono mt-2">{alertReports}</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-2xl bg-surface-container-low border border-white/5">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            type="button"
            onClick={() => setStatusFilter('ALL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${statusFilter === 'ALL' ? 'bg-primary text-black' : 'bg-surface-container text-slate-300 hover:text-white'}`}
          >
            All Reports ({totalReports})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('PENDING')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${statusFilter === 'PENDING' ? 'bg-amber-500 text-black' : 'bg-surface-container text-slate-300 hover:text-white'}`}
          >
            Pending ({pendingReports})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('VERIFIED')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${statusFilter === 'VERIFIED' ? 'bg-emerald-500 text-black' : 'bg-surface-container text-slate-300 hover:text-white'}`}
          >
            Verified ({verifiedReports})
          </button>
        </div>

        <div className="relative w-full sm:w-72">
          <span className="material-symbols-outlined absolute left-3 top-2.5 text-slate-400 text-base">search</span>
          <input
            type="text"
            placeholder="Search ear tag, disease, case #..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-surface-container border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>

      {/* Case Table */}
      <div className="bg-surface-container-low border border-white/5 rounded-2xl overflow-hidden shadow-card-subtle">
        {loading ? (
          <div className="p-12 text-center text-slate-400 space-y-2">
            <span className="material-symbols-outlined text-3xl text-primary animate-spin">progress_activity</span>
            <p className="text-xs font-bold font-mono uppercase tracking-wider">Loading diagnostic case history...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center text-red-400 space-y-2">
            <span className="material-symbols-outlined text-3xl">error</span>
            <p className="text-xs">{error}</p>
          </div>
        ) : filteredCases.length === 0 ? (
          <div className="p-12 text-center text-slate-400 space-y-3">
            <span className="material-symbols-outlined text-4xl text-slate-500">history_edu</span>
            <p className="text-sm font-bold text-white">No diagnostic cases found</p>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              {searchQuery ? 'No cases match your search query.' : 'Run your first AI Smart Diagnosis scan to record and send cases to your veterinarian.'}
            </p>
            <Link
              to="/health/diagnostics"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary/15 text-primary text-xs font-bold uppercase tracking-wider border border-primary/30 hover:bg-primary/25 transition-all mt-2"
            >
              <span className="material-symbols-outlined text-sm">add</span>
              <span>Start Diagnostic Scan</span>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-surface-container text-slate-400 uppercase text-[10px] tracking-wider border-b border-white/5 font-mono">
                <tr>
                  <th className="py-3 px-4">Case #</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Subject Animal</th>
                  <th className="py-3 px-4">AI Diagnosis</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Verification Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredCases.map((rec) => {
                  const isVer = Boolean(rec.verified);
                  const isHealthy = (rec.disease_name || '').toLowerCase().includes('healthy');
                  return (
                    <tr
                      key={rec.id}
                      onClick={() => {
                        setSelectedCase(rec);
                        setActiveImageTab(rec.symptoms_image ? 'symptoms' : 'cropped');
                      }}
                      className="hover:bg-surface-container/60 cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-4 font-mono font-bold text-primary">{rec.case_number || rec.id.slice(-6)}</td>
                      <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">{rec.created_at?.split(' ')[0] || '2026-08-24'}</td>
                      <td className="py-3 px-4">
                        <div className="font-bold text-white font-mono">{rec.animal_identifier || 'COW-TAG'}</div>
                        <div className="text-[10px] text-slate-400">{rec.breed || 'Dairy Breed'}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`font-bold ${isHealthy ? 'text-emerald-400' : 'text-white'}`}>
                          {rec.disease_name}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-primary">
                        {typeof rec.confidence === 'number' ? `${rec.confidence.toFixed(1)}%` : rec.confidence}
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-amber-500/10 text-amber-300 border border-amber-500/20">
                          {rec.severity || 'Moderate'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider inline-flex items-center gap-1 border ${
                            isVer
                              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                              : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                          }`}
                        >
                          <span className="material-symbols-outlined text-[12px]">{isVer ? 'verified' : 'pending'}</span>
                          {isVer ? 'Verified by Vet' : 'Pending Verification'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          className="px-2.5 py-1 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 text-[11px] font-bold inline-flex items-center gap-1 transition-all"
                        >
                          <span className="material-symbols-outlined text-sm">visibility</span>
                          <span>View Report</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detailed Case Report Modal */}
      {selectedCase && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-3 md:p-6 overflow-y-auto animate-fadeIn">
          <div className="bg-surface-container-low border border-primary/30 rounded-2xl max-w-4xl w-full shadow-2xl overflow-hidden my-auto flex flex-col max-h-[90vh]">
            {/* Header */}
            <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-surface-container">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/15 text-primary flex items-center justify-center border border-primary/30">
                  <span className="material-symbols-outlined text-2xl">medical_services</span>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-primary">{selectedCase.case_number || selectedCase.id}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase border ${
                        selectedCase.verified
                          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                          : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                      }`}
                    >
                      {selectedCase.verified ? 'Verified by Vet' : 'Pending Verification'}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-white">Livestock Pathology Disease Report</h2>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setSelectedCase(null)}
                className="w-8 h-8 rounded-lg bg-surface-container-highest hover:bg-surface-bright text-slate-400 hover:text-white flex items-center justify-center transition-all"
              >
                <span className="material-symbols-outlined text-lg">close</span>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 no-scrollbar">
              {/* Metadata Strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-surface-container border border-white/5 text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Subject Animal</span>
                  <span className="font-bold text-white font-mono">{selectedCase.animal_identifier || 'COW-TAG'}</span>
                  <span className="text-slate-400 text-[10px] block">{selectedCase.breed || 'Dairy Breed'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Report Date</span>
                  <span className="font-bold text-white font-mono">{selectedCase.created_at || '2026-08-24'}</span>
                  <span className="text-primary text-[10px] block">AI Telemetry</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Reported By</span>
                  <span className="font-bold text-white">{selectedCase.reported_by === 'vet' ? 'Veterinarian' : 'Farm Owner'}</span>
                  <span className="text-slate-400 font-mono text-[10px] block">{selectedCase.reporter_email || 'Owner Record'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Verifying Vet</span>
                  <span className={`font-bold ${selectedCase.verified ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {selectedCase.vet_name || 'Pending Review'}
                  </span>
                  <span className="text-slate-400 font-mono text-[10px] block">{selectedCase.vet_license || 'Awaiting Sign-off'}</span>
                </div>
              </div>

              {/* Imagery & Pathology Section */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left: Imagery */}
                <div className="lg:col-span-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-primary text-sm">photo_camera</span>
                      Visual Telemetry
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

                  <div className="relative rounded-xl overflow-hidden border border-white/10 bg-black/60 aspect-[4/3] flex items-center justify-center shadow-xl">
                    <img
                      src={displayModalImage}
                      alt="Cattle Clinical Diagnostics"
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute top-2 left-2 px-2 py-1 rounded bg-black/70 backdrop-blur-sm text-[10px] font-mono text-primary font-bold border border-white/10 flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                      <span>{activeImageTab === 'symptoms' ? 'Mask R-CNN Segment' : 'Bovine ROI Detection'}</span>
                    </div>
                  </div>
                </div>

                {/* Right: Pathological Telemetry */}
                <div className="lg:col-span-7 space-y-4">
                  <div className="p-4 rounded-xl bg-surface-container border border-primary/20 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-3xs font-mono font-bold uppercase tracking-widest text-primary">Diagnosed Condition</span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-primary/10 text-primary border border-primary/20">
                        {typeof selectedCase.confidence === 'number' ? `${selectedCase.confidence.toFixed(1)}%` : selectedCase.confidence} Confidence
                      </span>
                    </div>

                    <div>
                      <h3 className="text-xl font-extrabold text-white tracking-tight">{selectedCase.disease_name}</h3>
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
                        <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block mb-0.5">Diagnostic Rationale</span>
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

                  {selectedCase.clinical_notes && (
                    <div className="p-3.5 rounded-xl bg-surface-container border border-white/5 space-y-1">
                      <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">Clinical Notes</span>
                      <p className="text-xs text-slate-300 leading-relaxed">{selectedCase.clinical_notes}</p>
                    </div>
                  )}

                  {selectedCase.llm_reasoning && (
                    <div className="p-3.5 rounded-xl bg-surface-container border border-white/5 space-y-1">
                      <span className="text-[10px] text-primary uppercase font-bold tracking-wider flex items-center gap-1">
                        <span className="material-symbols-outlined text-xs">psychology</span>
                        AI Clinical Reasoning Briefing
                      </span>
                      <div className="text-xs text-slate-300 leading-relaxed max-h-32 overflow-y-auto no-scrollbar font-mono text-[11px] bg-black/40 p-2.5 rounded-lg border border-white/5 whitespace-pre-wrap">
                        {typeof selectedCase.llm_reasoning === 'string' ? selectedCase.llm_reasoning : JSON.stringify(selectedCase.llm_reasoning, null, 2)}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-white/10 bg-surface-container flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => setSelectedCase(null)}
                className="px-4 py-2.5 rounded-xl bg-surface-container-highest hover:bg-surface-bright text-slate-300 hover:text-white font-semibold text-xs transition-all"
              >
                Close Report
              </button>

              {selectedCase.cattle_id && (
                <button
                  type="button"
                  onClick={() => {
                    const cId = selectedCase.cattle_id;
                    setSelectedCase(null);
                    navigate(`/health/diagnostics?cattle_id=${cId}`);
                  }}
                  className="px-4 py-2.5 rounded-xl bg-primary text-black font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-primary/20 hover:brightness-110 active:scale-95 transition-all"
                >
                  <span className="material-symbols-outlined text-sm">refresh</span>
                  <span>Run New Scan for this Cattle</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
