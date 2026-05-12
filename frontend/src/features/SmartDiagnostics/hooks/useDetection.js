import { useState } from 'react'
import { detectImage } from '../services/api'

export default function useDetection() {
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function detect(file) {
    setStatus('processing')
    setError(null)
    try {
      const data = await detectImage(file)
      setResult(data)
      setStatus('done')
    } catch (err) {
      setError(err.message || String(err))
      setStatus('error')
    }
  }

  function reset() {
    setStatus('idle')
    setResult(null)
    setError(null)
  }

  return { status, result, error, detect, reset }
}
