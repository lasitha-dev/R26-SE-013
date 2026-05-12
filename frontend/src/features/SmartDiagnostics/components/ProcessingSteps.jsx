import React from 'react'

export default function ProcessingSteps() {
  return (
    <div className="pipeline">
      <div className="step active">
        <div className="step-icon">
          <i data-lucide="scan-line" />
        </div>
        <div className="step-details">
          <h3>Running YOLO Detection</h3>
          <p>Scanning image for cattle using YOLOv8...</p>
          <div className="progress-bar-container">
            <div className="progress-bar" style={{ width: '60%' }} />
          </div>
        </div>
      </div>

      <div className="step">
        <div className="step-icon">
          <i data-lucide="brain" />
        </div>
        <div className="step-details">
          <h3>Vision Transformer Classification</h3>
          <p>Classifying disease using ViT-B/16...</p>
          <div className="progress-bar-container">
            <div className="progress-bar" style={{ width: '0%' }} />
          </div>
        </div>
      </div>
    </div>
  )
}
