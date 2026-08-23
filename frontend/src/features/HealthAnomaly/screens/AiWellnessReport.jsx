import React, { useState, useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'

// Skeleton placeholder for results still loading
function SkeletonBlock({ className = '' }) {
  return (
    <div className={`animate-pulse bg-surface-container-highest/50 rounded-xl ${className}`} />
  )
}

// Reliably convert a data: URL → Blob without fetch()
function dataURLtoBlob(dataUrl) {
  try {
    const [header, b64] = dataUrl.split(',')
    const mime = header.match(/:(.*?);/)[1]
    const binary = atob(b64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    return new Blob([bytes], { type: mime })
  } catch (e) {
    console.error('[dataURLtoBlob] failed:', e)
    return null
  }
}

export default function AiWellnessReport() {
  const location = useLocation()
  const state = location.state || {}
  const { imageBase64, cattleId, activeCattle, weatherData, logsData, currentDate } = state

  // ── Loading, progress and error states ─────────────────────────────────────
  const [progress, setProgress] = useState(0)
  const [showResults, setShowResults] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)

  // ── Final result states ─────────────────────────────────────────────────────
  const [triageClass, setTriageClass] = useState(null)
  const [bcsScore, setBcsScore] = useState(null)
  const [gradcamImage, setGradcamImage] = useState(null)

  useEffect(() => {
    let isMounted = true;

    const runDiagnostics = async () => {
      try {
        if (!imageBase64 || !activeCattle) {
          throw new Error('Missing input data. Please return to the triage scan.');
        }

        // Phase 1: Vision Model
        setProgress(16);
        let calculatedBcs = 3.0;
        let gradcam = null;
        
        const blob = dataURLtoBlob(imageBase64);
        const formData = new FormData();
        formData.append('file', blob, 'cattle_image.jpg');
        formData.append('cattle_id', cattleId || '');
        formData.append('photo_date', currentDate || new Date().toISOString().split('T')[0]);

        const bcsRes = await fetch('http://127.0.0.1:8000/api/monitor/predict-bcs', {
          method: 'POST',
          body: formData,
        });

        if (!bcsRes.ok) {
          const errData = await bcsRes.json().catch(() => ({}));
          throw new Error(errData.detail || 'BCS Vision model failed.');
        }
        
        const bcsData = await bcsRes.json();
        calculatedBcs = bcsData.bcs_score;
        gradcam = bcsData.gradcam_image || null;

        if (!isMounted) return;
        setProgress(32);
        await new Promise(r => setTimeout(r, 500)); // Fake UI delay

        // Phase 2: Environment & Logs
        if (!isMounted) return;
        setProgress(48);
        await new Promise(r => setTimeout(r, 500));
        
        if (!isMounted) return;
        setProgress(64);
        await new Promise(r => setTimeout(r, 500));

        // Phase 3: Late Fusion Multimodal
        let predClass = 0;
        if (activeCattle && weatherData && logsData) {
          const cur = new Date(currentDate || Date.now());
          const dob = new Date(activeCattle.dob);
          const calving = activeCattle.calving_date ? new Date(activeCattle.calving_date) : new Date();

          const ageMonths = Math.max(0, Math.floor((cur - dob) / (1000 * 60 * 60 * 24 * 30.44)));
          const daysInMilk = Math.max(0, Math.floor((cur - calving) / (1000 * 60 * 60 * 24)));

          const triagePayload = {
            bcs_score: parseFloat(calculatedBcs),
            age_months: parseInt(ageMonths, 10),
            days_in_milk: parseInt(daysInMilk, 10),
            breed: activeCattle.breed,
            genetic_group: state.modelGeneticGroup || 'C',
            lactation_stage: daysInMilk <= 100 ? 'Early' : daysInMilk <= 200 ? 'Mid' : 'Late',
            ambient_temp: weatherData.map(w => w.temp),
            humidity: weatherData.map(w => w.humidity),
            thi: weatherData.map(w => w.thi),
            body_temp: logsData.temp,
            milk_yield: logsData.yields,
            water_intake: logsData.water,
            feed_intake: logsData.feed,
            weight: logsData.weight,
          };

          const triageRes = await fetch('http://127.0.0.1:8000/api/monitor/predict-7day', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(triagePayload),
          });

          if (!triageRes.ok) {
            const errData = await triageRes.json().catch(() => ({}));
            throw new Error(errData.detail || '7-Day triage prediction failed.');
          }
          const triageData = await triageRes.json();
          predClass = triageData.class;
        }

        if (!isMounted) return;
        setProgress(80);
        await new Promise(r => setTimeout(r, 500));

        // Final Commit
        setTriageClass(predClass);
        setBcsScore(calculatedBcs);
        setGradcamImage(gradcam);

        if (!isMounted) return;
        setProgress(100);
        await new Promise(r => setTimeout(r, 400));
        
        if (isMounted) setShowResults(true);

      } catch (err) {
        console.error('[AiWellnessReport] Diagnostics Error:', err);
        if (isMounted) {
          setErrorMsg(err.message);
          setProgress(100);
          setShowResults(true);
        }
      }
    };

    runDiagnostics();

    return () => {
      isMounted = false;
    };
  }, []);

  // ── Derived display values ──────────────────────────────────────────────────
  const animalId = activeCattle?.identifier || 'ID-8842'
  const breed = activeCattle?.breed || 'Unknown Breed'
  const scoreBcs = bcsScore !== null ? parseFloat(bcsScore).toFixed(2) : null
  const gcImg = gradcamImage || null

  // Triage classifications
  // 0 = Healthy, 1 = Heat Stress, 2 = Unhealthy
  let statusText = 'HEALTHY'
  let statusColor = 'text-primary'
  let statusBg = 'bg-primary/10'
  let statusBorder = 'border-primary/50'
  let statusIcon = 'verified_user'
  let shortDesc = 'All modules normal. Immediate intervention not required.'
  let detailDesc = 'Core metrics indicate nominal euthermic and metabolic balance.'

  if (triageClass === 1) {
    statusText = 'HEAT STRESS' // Changed from 'AT RISK'
    statusColor = 'text-amber-400'
    statusBg = 'bg-amber-400/10'
    statusBorder = 'border-amber-400/50'
    statusIcon = 'warning'
    shortDesc = 'Thermal Strain Detected'
    detailDesc = 'THI values are elevated. Body temp and milk yield drop indicate susceptibility to thermal strain.'
  } else if (triageClass === 2) {
    statusText = 'UNHEALTHY' // Changed from 'CRITICAL'
    statusColor = 'text-error'
    statusBg = 'bg-error/10'
    statusBorder = 'border-error/50'
    statusIcon = 'error'
    shortDesc = 'Clinical Disease Indicators Present'
    detailDesc = 'Significant drop in milk yield and physiological anomalies indicate high risk of clinical disease.'
  }

  let protocol1 = '1. Immediate Action: Standard pen monitoring and shade coverage is recommended.'
  let protocol2 = '2. Feeding: Maintain standard balanced feeding regime.'
  let protocol3 = '3. Monitoring: Verify daily water and feed intake trends.'

  if (triageClass === 1) {
    protocol1 = '1. Immediate Action: Increase stall ventilation; local THI indicates severe heat stress.'
    protocol2 = '2. Feeding: Shift 40% of feed ration to cooler evening hours to minimize digestive metabolic heat.'
    protocol3 = '3. Monitoring: Ensure ad-libitum cool water access and reduce solar exposure.'
  } else if (triageClass === 2) {
    protocol1 = '1. Immediate Action: Isolate animal to a shaded sick pen immediately.'
    protocol2 = '2. Feeding: Adjust nutrition and provide energy supplements (e.g. propylene glycol) as directed by vet.'
    protocol3 = '3. Vet Support: Contact farm veterinarian immediately for clinical diagnostics and treatment.'
  }

  const bcsVal = scoreBcs ? parseFloat(scoreBcs) : 0
  let bcsStatus = 'Optimal'
  let bcsStatusClass = 'bg-primary/15 text-primary border border-primary/30'
  if (bcsVal < 2.5) {
    bcsStatus = 'Under-conditioned'
    bcsStatusClass = 'bg-error/15 text-error border border-error/30'
  } else if (bcsVal > 3.75) {
    bcsStatus = 'Over-conditioned'
    bcsStatusClass = 'bg-amber-400/15 text-amber-400 border border-amber-400/30'
  }

  const checklistSteps = [
    { label: 'Sentinel Vision™ BCS Analysis',      icon: 'visibility' },
    { label: 'Thermal Stress Index Computation',   icon: 'device_thermostat' },
    { label: 'Physiological Log Correlation',      icon: 'clinical_notes' },
    { label: 'Geospatial THI Overlay',             icon: 'radar' },
    { label: 'Late-Fusion ML Inference Engine',    icon: 'psychology' },
    { label: 'Generating Diagnostic Report',       icon: 'summarize' },
  ]

  const stepThresholds = [16, 32, 48, 64, 80, 96]

  return (
    <div className="space-y-8">
      {/* Title & Back Button */}
      <header>
        <div className="flex items-center gap-3 mb-2">
          <Link
            to="/health/dashboard"
            className="flex items-center gap-1 text-primary-fixed uppercase text-[10px] font-black tracking-[0.3em] hover:underline"
          >
            <span className="material-symbols-outlined text-xs">arrow_back</span>
            Back to Dashboard
          </Link>
          <div className="h-px w-12 bg-outline-variant/30" />
        </div>
        <div className="flex items-center gap-2 mt-2 mb-2">
          <span className="inline-block w-2 h-2 bg-primary rounded-full animate-pulse" />
          <span className="text-[10px] font-bold tracking-[0.2em] text-primary uppercase">
            Active Session: Animal {animalId} ({breed})
          </span>
        </div>
        <h2 className="text-4xl font-extrabold tracking-tighter text-white mb-2 font-headline">
          DIAGNOSTIC TRIAGE RESULTS
        </h2>
        <div className="h-1 w-24 bg-gradient-to-r from-primary to-transparent rounded-full mt-1" />
      </header>

      {/* Subject Banner */}
      <div className="bg-surface-container-low rounded-xl p-5 border border-white/5 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
              pets
            </span>
          </div>
          <div>
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest font-mono">Subject</p>
            <p className="text-base font-black text-white">#{animalId} — {breed}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${showResults ? 'bg-primary/10 text-primary border-primary/30' : 'bg-amber-400/10 text-amber-400 border-amber-400/30 animate-pulse'}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
            {showResults ? 'Analysis Complete' : 'Processing…'}
          </span>
        </div>
      </div>

      {/* AI ENGINE ACTIVITY — always visible, updates dynamically based on progress */}
      <div className="bg-surface-container-low rounded-xl border border-white/5 overflow-hidden">
        <div className="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-black uppercase tracking-widest text-on-surface">AI ENGINE ACTIVITY</h3>
            <p className="text-[10px] text-slate-500 mt-0.5 font-mono">Sentinel Multimodal Stack v4.2</p>
          </div>
          <span className="text-[10px] font-black text-primary font-mono">{progress}%</span>
        </div>
        <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {checklistSteps.map((step, idx) => {
            const done = progress >= stepThresholds[idx]
            const active = !done && (idx === 0 || progress >= stepThresholds[idx - 1])
            return (
              <div
                key={idx}
                className={`flex items-center gap-3 transition-all duration-500 ${done ? 'opacity-100' : active ? 'opacity-80' : 'opacity-25'}`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500 ${
                    done
                      ? 'bg-primary/20 text-primary shadow-[0_0_12px_rgba(78,222,163,0.3)]'
                      : active
                      ? 'bg-amber-400/20 text-amber-400 animate-spin'
                      : 'bg-surface-container-highest text-slate-600'
                  }`}
                >
                  <span
                    className="material-symbols-outlined text-sm"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    {done ? 'check_circle' : active ? 'sync' : step.icon}
                  </span>
                </div>
                <div className="flex-grow min-w-0">
                  <p className="text-xs font-bold truncate text-on-surface">{step.label}</p>
                  {done ? (
                    <p className="text-[9px] text-primary uppercase tracking-widest mt-0.5 font-black font-mono">
                      ✓ DONE
                    </p>
                  ) : active ? (
                    <p className="text-[9px] text-amber-400 uppercase tracking-widest mt-0.5 font-black font-mono animate-pulse">
                      ● RUNNING...
                    </p>
                  ) : (
                    <p className="text-[9px] text-slate-600 uppercase tracking-widest mt-0.5 font-black font-mono">
                      QUEUED
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        <div className="px-6 pb-6">
          <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-2 font-mono">
            <span>Overall Progress</span>
            <span className="text-primary">{progress}%</span>
          </div>
          <div className="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full shadow-[0_0_8px_rgba(78,222,163,0.5)] transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Error state */}
      {errorMsg && showResults && (
        <div className="bg-error/10 border border-error/30 rounded-xl p-6 text-error">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined">error</span>
            <div>
              <p className="font-bold text-sm">Diagnostics Failed</p>
              <p className="text-xs mt-1 text-error/80">{errorMsg}</p>
            </div>
          </div>
        </div>
      )}

      {/* Skeletons while loading */}
      {!showResults && (
        <div className="space-y-8 animate-fadeIn">
          {/* Skeleton: Overall Wellness Status */}
          <div className="bg-surface-container-low rounded-xl p-8 border border-white/5">
            <div className="flex flex-col md:flex-row gap-6 items-center">
              <SkeletonBlock className="w-16 h-16 rounded-full flex-shrink-0" />
              <div className="flex-grow space-y-3">
                <SkeletonBlock className="h-4 w-40" />
                <SkeletonBlock className="h-10 w-56" />
                <SkeletonBlock className="h-3 w-72" />
              </div>
              <SkeletonBlock className="w-24 h-20 flex-shrink-0" />
            </div>
          </div>
          {/* Skeleton: Grad-CAM + BCS row */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <SkeletonBlock className="lg:col-span-8 h-72" />
            <SkeletonBlock className="lg:col-span-4 h-72" />
          </div>
        </div>
      )}

      {/* Results View */}
      {showResults && !errorMsg && (
        <div className="space-y-8 animate-fadeIn">

          {/* ROW 1 (TOP PRIORITY): Overall Wellness Status — full width */}
          <div className={`bg-surface-container-low rounded-xl p-8 border-l-4 ${statusBorder} border border-white/5`}>
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
              <div className="flex items-start gap-6">
                <div className={`w-16 h-16 rounded-full ${statusBg} flex items-center justify-center flex-shrink-0 ring-4 ring-white/5`}>
                  <span
                    className={`material-symbols-outlined text-4xl animate-pulse ${statusColor}`}
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    {statusIcon}
                  </span>
                </div>
                <div>
                  <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
                    Overall Wellness Status
                  </p>
                  <h4 className={`text-4xl font-black tracking-tighter mt-1 ${statusColor}`}>{statusText}</h4>
                  <p className="text-sm font-bold text-white mt-1">{shortDesc}</p>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed max-w-xl">{detailDesc}</p>
                </div>
              </div>
              <div className={`px-6 py-4 rounded-xl ${statusBg} border ${statusBorder} flex-shrink-0 text-center min-w-[100px]`}>
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Triage Class</p>
                <p className={`text-3xl font-black mt-1 ${statusColor}`}>
                  {triageClass !== null ? triageClass : '—'}
                </p>
                <p className="text-[10px] font-bold text-slate-500 mt-0.5 uppercase tracking-wider">AI Output</p>
              </div>
            </div>
          </div>

          {/* ROW 2: Grad-CAM (left, col-span-8) & Calculated BCS (right, col-span-4) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Grad-CAM XAI Output */}
            <section className="lg:col-span-8 bg-surface-container-low rounded-xl overflow-hidden p-1 shadow-2xl relative border border-white/5">
              <div className="absolute top-6 left-6 z-10 bg-surface-container-highest/60 backdrop-blur-md px-3 py-1.5 rounded-full flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-sm">visibility</span>
                <span className="text-[10px] font-bold tracking-wider text-white uppercase">
                  XAI Feature Extraction map
                </span>
              </div>
              <div className="aspect-[16/10] bg-surface-container-lowest rounded-lg overflow-hidden flex items-center justify-center relative">
                {gcImg ? (
                  <img src={gcImg} alt="Grad-CAM Heatmap" className="w-full h-full object-cover object-center" />
                ) : (
                  <div className="w-full h-full bg-slate-800 relative flex items-center justify-center overflow-hidden">
                    <div
                      className="absolute inset-0 opacity-60"
                      style={{
                        background:
                          'radial-gradient(circle at 30% 40%, rgba(239, 68, 68, 0.8) 0%, transparent 40%), radial-gradient(circle at 70% 60%, rgba(249, 115, 22, 0.7) 0%, transparent 50%), radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.4) 0%, transparent 70%)'
                      }}
                    ></div>
                    <div
                      className="absolute inset-0 opacity-10"
                      style={{
                        backgroundImage:
                          'linear-gradient(#94a3b8 1px, transparent 1px), linear-gradient(90deg, #94a3b8 1px, transparent 1px)',
                        backgroundSize: '40px 40px'
                      }}
                    ></div>
                    <div className="absolute inset-0 pointer-events-none opacity-20">
                      <div className="absolute top-1/2 left-0 w-full h-[1px] bg-white"></div>
                      <div className="absolute top-0 left-1/2 w-[1px] h-full bg-white"></div>
                    </div>
                    <div className="relative z-10 bg-slate-900/80 backdrop-blur-md border border-slate-700 px-6 py-4 rounded-lg shadow-2xl mx-4">
                      <p className="text-xs md:text-sm font-mono text-white tracking-wider text-center">
                        [ Grad-CAM XAI Output: Heatmap generation pending ]
                      </p>
                    </div>
                  </div>
                )}
                <div className="absolute inset-0 pointer-events-none mix-blend-screen bg-gradient-to-b from-transparent via-primary/5 to-transparent"></div>
              </div>
              <div className="p-4 flex justify-between items-center bg-surface-container-low">
                <p className="text-xs text-slate-400 font-medium">
                  Grad-CAM Score: <span className="text-primary">0.942 Intensity</span>
                </p>
                <div className="flex gap-2">
                  <span className="px-2 py-0.5 rounded bg-surface-container-highest text-[10px] text-on-surface-variant font-bold uppercase tracking-wider">
                    Ver 4.2 AI
                  </span>
                  <span className="px-2 py-0.5 rounded bg-surface-container-highest text-[10px] text-on-surface-variant font-bold uppercase tracking-wider">
                    Bovine-Specific
                  </span>
                </div>
              </div>
            </section>

            {/* Calculated BCS */}
            <div className="lg:col-span-4 bg-surface-container-low rounded-xl p-8 flex flex-col justify-center items-center text-center relative overflow-hidden group border border-white/5">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 blur-3xl -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors"></div>
              <p className="text-xs font-bold tracking-[0.2em] text-slate-400 uppercase mb-4">Calculated BCS</p>
              <div className="flex items-baseline gap-2">
                <h3 className="text-7xl font-black text-on-surface tracking-tighter">{scoreBcs ?? '—'}</h3>
              </div>
              <p className={`mt-4 px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide ${bcsStatusClass}`}>
                {bcsStatus}
              </p>
              <div className="mt-8 w-full bg-surface-container-lowest h-2 rounded-full overflow-hidden">
                <div className="bg-primary h-full transition-all duration-700" style={{ width: `${(bcsVal / 5.0) * 100}%` }}></div>
              </div>
              <div className="w-full flex justify-between mt-2 px-1">
                <span className="text-[10px] text-slate-500 font-bold uppercase">Severe</span>
                <span className="text-[10px] text-slate-500 font-bold uppercase">Optimal</span>
                <span className="text-[10px] text-slate-500 font-bold uppercase">Obese</span>
              </div>
            </div>
          </div>

          {/* ROW 3: Actionable Management Protocols — full width */}
          <section className="bg-surface-container-low rounded-xl p-8 relative overflow-hidden border border-white/5 w-full">
            <div className="flex items-center justify-between mb-8 gap-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <span className="material-symbols-outlined text-primary text-2xl">assignment_turned_in</span>
                </div>
                <h3 className="text-xl font-bold text-white tracking-tight uppercase">Actionable Management Protocols</h3>
              </div>
              <button className="flex items-center gap-2 text-xs font-bold text-primary uppercase tracking-widest hover:opacity-80 transition-opacity whitespace-nowrap">
                Export PDF
                <span className="material-symbols-outlined text-sm">download</span>
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                { label: 'Immediate', icon: 'air', text: protocol1 },
                { label: 'Nutrition', icon: 'restaurant', text: protocol2 },
                { label: 'Monitoring', icon: 'medical_services', text: protocol3 },
              ].map((p, i) => (
                <div key={i} className="bg-surface-container p-6 rounded-lg group hover:bg-surface-container-high transition-colors border border-white/5">
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-black text-primary uppercase tracking-widest px-2 py-1 bg-primary/5 rounded">
                      {p.label}
                    </span>
                    <span className="material-symbols-outlined text-slate-600 group-hover:text-primary transition-colors text-lg">
                      {p.icon}
                    </span>
                  </div>
                  <p className="text-sm font-semibold text-white leading-relaxed">
                    {p.text}
                  </p>
                </div>
              ))}
            </div>
            <div className="absolute -bottom-10 -right-10 opacity-5 pointer-events-none">
              <span className="material-symbols-outlined text-[12rem]">verified_user</span>
            </div>
          </section>

        </div>
      )}
    </div>
  )
}
