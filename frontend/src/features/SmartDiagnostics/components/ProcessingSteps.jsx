import React from 'react'

export default function ProcessingSteps() {
  return (
    <div className="mt-4">
      <div className="mb-2">Running YOLO detection...</div>
      <div className="w-full bg-gray-200 h-2 mb-4"><div className="bg-green-500 h-2 w-2/5" /></div>

      <div className="mb-2">Running Transformer classification...</div>
      <div className="w-full bg-gray-200 h-2"><div className="bg-indigo-500 h-2 w-1/3" /></div>
    </div>
  )
}
