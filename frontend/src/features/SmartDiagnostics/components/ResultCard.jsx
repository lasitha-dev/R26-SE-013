import React from 'react'

function ProbList({ probs }) {
  const entries = Object.entries(probs || {})
  entries.sort((a, b) => b[1] - a[1])
  return (
    <ul className="mt-3">
      {entries.map(([name, val]) => (
        <li key={name} className={`flex justify-between ${name === 'Healthy' ? 'font-semibold' : ''}`}>
          <span>{name}</span>
          <span>{val}%</span>
        </li>
      ))}
    </ul>
  )
}

export default function ResultCard({ data }) {
  const best = data.best_detection
  const disease = data.disease

  return (
    <div className="border p-4 rounded">
      <div className="flex gap-4">
        <div className="w-48 h-48 bg-gray-100 flex items-center justify-center">
          {data.cropped_image ? (
            // eslint-disable-next-line jsx-a11y/img-redundant-alt
            <img src={data.cropped_image} alt="cropped" className="max-h-full max-w-full" />
          ) : (
            <div>No crop</div>
          )}
        </div>

        <div className="flex-1">
          <div className="text-lg font-semibold">Diagnosis: {disease?.name}</div>
          <div className="text-sm text-gray-600">Confidence: {disease?.confidence}%</div>
          <ProbList probs={disease?.all_probabilities} />
        </div>
      </div>
    </div>
  )
}
