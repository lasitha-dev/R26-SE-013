import React, { useRef, useState } from 'react'

export default function UploadDropzone({ onFile, disabled = false }) {
  const fileRef = useRef(null)
  const [dragover, setDragover] = useState(false)

  function handleChange(e) {
    const f = e.target.files && e.target.files[0]
    if (f && onFile) onFile(f)
  }

  function handleClick() {
    if (fileRef.current) fileRef.current.click()
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragover(false)
    const f = e.dataTransfer.files && e.dataTransfer.files[0]
    if (f && onFile) onFile(f)
  }

  function handleDragOver(e) {
    e.preventDefault()
    setDragover(true)
  }

  function handleDragLeave() {
    setDragover(false)
  }

  return (
    <div
      className={`dropzone${dragover ? ' dragover' : ''}`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={handleClick}
    >
      <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleChange} />
      <i data-lucide="upload-cloud" className="upload-icon" />
      <p>Drag an image here or</p>
      <span>Supported: JPG, PNG, JPEG</span>
      <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); handleClick() }} disabled={disabled}>
        Choose Image
      </button>
    </div>
  )
}
