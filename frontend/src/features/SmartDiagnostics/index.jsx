import React from 'react'
import UploadDropzone from './components/UploadDropzone'
import ResultCard from './components/ResultCard'
import ProcessingSteps from './components/ProcessingSteps'
import useDetection from './hooks/useDetection'
import FullLayout from './components/FullLayout'

export default function SmartDiagnostics() {
  const { status, result, error, detect, reset } = useDetection()

  return (
    <FullLayout>
      <section id="upload-section" className="card">
        <h2>1. Upload Image</h2>
        <p className="instruction">Upload a clear photo of the cattle for analysis.</p>
        <UploadDropzone onFile={detect} disabled={status === 'processing'} />
      </section>

      {status === 'processing' && (
        <section id="processing-section" className="card active mt-6">
          <h2>Processing Analysis</h2>
          <div className="image-preview-container">
            <img id="preview-image" src={result?.image ?? ''} alt="Preview" />
            <div className="scanner-line" />
          </div>
          <ProcessingSteps />
        </section>
      )}

      {status === 'done' && result && (
        <section id="result-section" className="card mt-6">
          <div className="result-header">
            <h2>Analysis Complete</h2>
            <button className="btn btn-outline" onClick={reset}>New Analysis</button>
          </div>
          <div className="result-content">
            <div className="result-images">
              <div className="result-image-wrapper">
                <span className="image-label">Original Image + YOLO Detection</span>
                <img id="result-image" src={result.image} alt="Result" />
                <div className="bounding-box" id="bounding-box">
                  <span className="box-label">Cattle</span>
                </div>
              </div>
              <div className="result-image-wrapper cropped-wrapper">
                <span className="image-label">Cropped Region → ViT Input</span>
                <img id="cropped-image" src={result.cropped_image} alt="Cropped region sent to Transformer" />
              </div>
            </div>

            <div className="result-details">
              <div className={`diagnosis-card ${result.disease?.name === 'Healthy' ? 'healthy' : ''}`}>
                <h3>Primary Diagnosis</h3>
                <div className={`disease-tag ${result.disease?.name === 'Healthy' ? 'healthy' : ''}`}>{result.disease?.name ?? '—'}</div>
                <div className="confidence-meter">
                  <div className="meter-header">
                    <span>Confidence Score</span>
                    <span className="score-value">{result.disease?.confidence ?? '—'}%</span>
                  </div>
                  <div className="meter-track"><div className={`meter-fill ${result.disease?.name === 'Healthy' ? 'healthy' : ''}`} style={{ width: `${result.disease?.confidence ?? 0}%` }} /></div>
                </div>
              </div>

              <div className="probabilities-card">
                <h4>All Class Probabilities</h4>
                <ul id="prob-list">
                  {Object.entries(result.disease?.all_probabilities || {}).sort((a,b)=>b[1]-a[1]).map(([name, val]) => (
                    <li key={name} className={`${name===result.disease?.name? 'highlight':''}`}>
                      <span className="prob-name">{name}</span>
                      <span className="prob-val">{val}%</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="model-info">
                <h4>Pipeline Details</h4>
                <ul>
                  <li><i data-lucide="check-circle-2"></i> <strong>Tier 1 Detector:</strong> best.pt (YOLOv8)</li>
                  <li><i data-lucide="check-circle-2"></i> <strong>Tier 2 Classifier:</strong> ViT-B/16</li>
                  <li><i data-lucide="cpu"></i> <strong>Device:</strong> <span id="device-info">{result.device}</span></li>
                  <li><i data-lucide="clock"></i> <strong>Processing Time:</strong> <span id="processing-time">{result.processing_time ?? '—'}</span></li>
                  <li><i data-lucide="layers"></i> <strong>Total Detections:</strong> <span id="total-detections">{result.detections?.length ?? 0}</span></li>
                </ul>
              </div>
            </div>
          </div>
        </section>
      )}

      {status === 'error' && (
        <div className="mt-4 text-red-600">Error: {error}</div>
      )}
    </FullLayout>
  )
}
