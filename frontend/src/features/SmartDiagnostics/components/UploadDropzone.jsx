import React, { useRef } from 'react'

export default function UploadDropzone({ onFile, disabled = false }) {
  const fileRef = useRef(null)

  function handleChange(e) {
    const f = e.target.files && e.target.files[0]
    if (f && onFile) onFile(f)
  }

  function handleClick() {
    if (fileRef.current) fileRef.current.click()
  }

  return (
    <div className="border-2 border-dashed p-6 rounded text-center">
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleChange} />
      <p className="mb-2">Drag an image here or</p>
      <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={handleClick} disabled={disabled}>Choose image</button>
    </div>
  )
}
