import React from 'react'
import UploadDropzone from './components/UploadDropzone'
import ResultCard from './components/ResultCard'
import ProcessingSteps from './components/ProcessingSteps'
import useDetection from './hooks/useDetection'

export default function SmartDiagnostics() {
  const { status, result, error, detect, reset } = useDetection()

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold mb-4">Smart Diagnostics</h2>

      <UploadDropzone onFile={detect} disabled={status === 'processing'} />

      {status === 'processing' && <ProcessingSteps />}

      {status === 'done' && result && (
        <div className="mt-6">
          <ResultCard data={result} />
          <button className="mt-4 px-4 py-2 bg-gray-200" onClick={reset}>Analyze another</button>
        </div>
      )}

      {status === 'error' && (
        <div className="mt-4 text-red-600">Error: {error}</div>
      )}
    </div>
  )
}
